import hashlib
import io
import json
import logging
import os
import re
import secrets
import sqlite3
import time
import urllib.parse
import urllib.request

import pyotp
import qrcode
import qrcode.image.svg
from dotenv import load_dotenv
from flask import (
    Flask,
    flash,
    g,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import check_password_hash, generate_password_hash

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(__file__)
DATABASE = os.environ.get("SQLITE_FILE_PATH") or os.path.join(
    BASE_DIR, "instance", "restaurants.db"
)

_types_mapping_path = os.path.join(BASE_DIR, "static", "types.json")
try:
    with open(_types_mapping_path) as _f:
        TYPES_MAPPING = json.load(_f)
except OSError:
    TYPES_MAPPING = {}


def _init_db(conn):
    """Create all tables and seed defaults. Safe to call on every connection."""
    conn.execute(
        """CREATE TABLE IF NOT EXISTS restaurants (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            address TEXT NOT NULL,
            city TEXT NOT NULL,
            map_uri TEXT,
            directions_uri TEXT,
            dining_options TEXT CHECK(dining_options IN ('dine-in','delivery','both')) NOT NULL,
            rating INTEGER CHECK(rating IS NULL OR (rating BETWEEN 1 AND 5)),
            wishlisted BOOLEAN NOT NULL DEFAULT 0,
            price_level INTEGER,
            notes TEXT,
            opening_hours TEXT,
            types TEXT,
            latitude REAL,
            longitude REAL,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP)
        )"""
    )

    cur = conn.execute("PRAGMA table_info(restaurants)")
    columns = [row[1] for row in cur.fetchall()]
    if "price_level" not in columns:
        conn.execute("ALTER TABLE restaurants ADD COLUMN price_level INTEGER")
    if "notes" not in columns:
        conn.execute("ALTER TABLE restaurants ADD COLUMN notes TEXT")
    if "opening_hours" not in columns:
        conn.execute("ALTER TABLE restaurants ADD COLUMN opening_hours TEXT")
    if "types" not in columns:
        conn.execute("ALTER TABLE restaurants ADD COLUMN types TEXT")
    if "latitude" not in columns:
        conn.execute("ALTER TABLE restaurants ADD COLUMN latitude REAL")
    if "longitude" not in columns:
        conn.execute("ALTER TABLE restaurants ADD COLUMN longitude REAL")
    if "type" in columns and "dining_options" not in columns:
        conn.execute("ALTER TABLE restaurants RENAME COLUMN type TO dining_options")
    if "wishlisted" not in columns:
        # Make rating nullable: add new nullable column, copy data, swap names
        conn.execute(
            "ALTER TABLE restaurants ADD COLUMN rating_new INTEGER CHECK(rating_new IS NULL OR (rating_new BETWEEN 1 AND 5))"
        )
        conn.execute("UPDATE restaurants SET rating_new = rating")
        conn.execute("ALTER TABLE restaurants DROP COLUMN rating")
        conn.execute("ALTER TABLE restaurants RENAME COLUMN rating_new TO rating")
        conn.execute(
            "ALTER TABLE restaurants ADD COLUMN wishlisted BOOLEAN NOT NULL DEFAULT 0"
        )

    conn.execute(
        """CREATE TABLE IF NOT EXISTS dishes (
            restaurant_id TEXT NOT NULL,
            name TEXT NOT NULL,
            rating INTEGER CHECK(rating IN (0, 1)) NOT NULL,
            notes TEXT,
            created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
            PRIMARY KEY (restaurant_id, name),
            FOREIGN KEY(restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
        )"""
    )

    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            secret_key TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            totp_secret TEXT
        )"""
    )
    conn.execute(
        "INSERT OR IGNORE INTO settings (id, secret_key, password_hash, totp_secret) VALUES (1, ?, ?, NULL)",
        (secrets.token_hex(32), generate_password_hash("letthemcook")),
    )
    conn.commit()
    return conn.execute("SELECT secret_key FROM settings WHERE id = 1").fetchone()[0]


def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


app = Flask(__name__, static_folder="static", template_folder="templates")
csrf = CSRFProtect(app)

app.logger.setLevel(logging.INFO)

# --- Auth setup ---
login_manager = LoginManager(app)
login_manager.login_view = "login"


class User(UserMixin):
    id = "admin"


_USER = User()


LOGIN_DISABLED = os.environ.get("DISABLE_LOGIN", "").lower() == "true"


@login_manager.user_loader
def load_user(user_id):
    if user_id == "admin":
        return _USER
    return None


@login_manager.unauthorized_handler
def unauthorized():
    if request.path.startswith("/api/"):
        return jsonify({"error": "unauthorized"}), 401
    return redirect(url_for("login"))


@app.before_request
def auto_login_if_disabled():
    if LOGIN_DISABLED and not current_user.is_authenticated:
        login_user(_USER)


def _file_hash(path):
    """Return a short MD5 hash of a file's contents."""
    try:
        with open(path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()[:8]
    except OSError:
        return "0"


@app.template_global()
def versioned_url(filename):
    """Return a versioned URL for a static file, e.g. /static/app.js?v=abc12345."""
    from flask import url_for

    path = os.path.join(app.static_folder, filename)
    return f"{url_for('static', filename=filename)}?v={_file_hash(path)}"


def snake_to_camel(snake_dict):
    """Convert dictionary keys from snake_case to camelCase"""
    camel_dict = {}
    for key, value in snake_dict.items():
        components = key.split("_")
        camel_key = components[0] + "".join(x.title() for x in components[1:])
        camel_dict[camel_key] = value
    return camel_dict


def parse_restaurant_row(row):
    """Convert a DB row to a dict with opening_hours and types deserialized."""
    d = dict(row)

    if d.get("opening_hours"):
        try:
            d["opening_hours"] = json.loads(d["opening_hours"])
        except (json.JSONDecodeError, TypeError):
            d["opening_hours"] = None

    if d.get("types"):
        try:
            d["types"] = json.loads(d["types"])
        except (json.JSONDecodeError, TypeError):
            d["types"] = []
    else:
        d["types"] = []

    cuisines = set()
    for t in d["types"]:
        cuisine = TYPES_MAPPING.get(t)
        if cuisine is not None:
            cuisines.add(cuisine)
    d["cuisines"] = sorted(cuisines)

    if "wishlisted" in d:
        d["wishlisted"] = bool(d["wishlisted"])

    return d


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def _get_settings(db):
    return dict(
        db.execute(
            "SELECT secret_key, password_hash, totp_secret FROM settings WHERE id = 1"
        ).fetchone()
    )


def _make_qr_svg(secret):
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name="admin", issuer_name="Let Them Cook")
    qr = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathImage)
    buf = io.BytesIO()
    qr.save(buf)
    return buf.getvalue().decode("utf-8")


@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    db = get_db()
    settings = _get_settings(db)
    totp_enabled = bool(settings.get("totp_secret"))

    if request.method == "POST":
        password = request.form.get("password", "")
        totp_code = request.form.get("totp_code", "").strip()

        password_ok = bool(settings["password_hash"]) and check_password_hash(
            settings["password_hash"], password
        )

        if settings["totp_secret"]:
            totp = pyotp.TOTP(settings["totp_secret"])
            totp_ok = totp.verify(totp_code, valid_window=1)
        else:
            totp_ok = True

        if password_ok and totp_ok:
            remember = request.form.get("remember") == "on"
            login_user(_USER, remember=remember)
            return redirect(url_for("index"))

        flash("Invalid credentials.", "error")
        return redirect(url_for("login"))

    return render_template("login.html", totp_enabled=totp_enabled)


@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


@app.route("/settings", methods=["GET", "POST"])
@login_required
def settings():
    if LOGIN_DISABLED:
        return "", 404
    db = get_db()
    settings = _get_settings(db)
    totp_enabled = bool(settings.get("totp_secret"))

    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm_password = request.form.get("confirm_password", "")

        if not check_password_hash(settings["password_hash"], current_password):
            flash("Current password is incorrect.", "error")
        elif len(new_password) < 8:
            flash("New password must be at least 8 characters.", "error")
        elif new_password != confirm_password:
            flash("New passwords do not match.", "error")
        elif settings["totp_secret"] and not pyotp.TOTP(settings["totp_secret"]).verify(
            request.form.get("totp_code", "").strip()
        ):
            flash("Invalid authenticator code.", "error")
        else:
            db.execute(
                "UPDATE settings SET password_hash = ? WHERE id = 1",
                (generate_password_hash(new_password),),
            )
            db.commit()
            flash("Password updated successfully.", "success")
        return redirect(url_for("settings"))

    return render_template(
        "settings.html",
        totp_enabled=totp_enabled,
    )


@app.route("/set-up-2fa", methods=["GET", "POST"])
@login_required
def set_up_2fa():
    if LOGIN_DISABLED:
        return "", 404
    db = get_db()

    if request.method == "POST":
        provisional_secret = session.get("provisional_totp_secret")
        totp_code = request.form.get("totp_code", "").strip()

        if not provisional_secret:
            return redirect(url_for("set_up_2fa"))

        totp = pyotp.TOTP(provisional_secret)
        if totp.verify(totp_code, valid_window=1):
            db.execute(
                "UPDATE settings SET totp_secret = ? WHERE id = 1",
                (provisional_secret,),
            )
            db.commit()
            session.pop("provisional_totp_secret", None)
            return redirect(url_for("settings"))
        else:
            flash("Invalid code. Please try again.", "set_up_2fa_error")
            return redirect(url_for("set_up_2fa"))

    provisional_secret = session.get("provisional_totp_secret") or pyotp.random_base32()
    session["provisional_totp_secret"] = provisional_secret
    qr_svg = _make_qr_svg(provisional_secret)
    return render_template("set_up_2fa.html", qr_svg=qr_svg, secret=provisional_secret)


@app.route("/disable-2fa", methods=["POST"])
@login_required
def disable_2fa():
    if LOGIN_DISABLED:
        return "", 404
    db = get_db()
    settings = _get_settings(db)
    totp = pyotp.TOTP(settings["totp_secret"])
    if not totp.verify(request.form.get("totp_code", "").strip(), valid_window=1):
        flash("Invalid authenticator code.", "totp_error")
        return redirect(url_for("settings"))
    db.execute("UPDATE settings SET totp_secret = NULL WHERE id = 1")
    db.commit()
    return redirect(url_for("settings"))


@app.route("/")
@login_required
def index():
    key = os.environ.get("GOOGLE_MAPS_API_KEY")
    map_id = os.environ.get("MAP_ID")
    restaurant_info = session.pop("share_restaurant_info", None)
    return render_template(
        "index.html",
        google_api_key=key,
        map_id=map_id,
        login_disabled=LOGIN_DISABLED,
        restaurant_info=restaurant_info,
    )


@app.route("/share-target")
@login_required
def share_target():
    text = request.args.get("text")
    url = request.args.get("url")
    restaurant_info = _resolve_restaurant_info(text, url) if (text or url) else None
    if restaurant_info:
        session["share_restaurant_info"] = restaurant_info
    return redirect(url_for("index"))


def _resolve_restaurant_info(text_param, url_param):
    """Follow a Maps short link and return the parsed place name+address, or None."""
    _ALLOWED_HOSTS = {"maps.app.goo.gl", "goo.gl", "google.com", "www.google.com"}

    maps_url = None
    candidates = ([url_param] if url_param else []) + re.findall(
        r"https?://\S+", text_param or ""
    )
    for candidate in candidates:
        try:
            host = urllib.parse.urlparse(candidate).netloc.lower().split(":")[0]
            if host in _ALLOWED_HOSTS:
                maps_url = candidate
                break
        except Exception:
            continue

    if not maps_url:
        return None

    # Short URLs may take a moment to propagate after creation — retry with
    # exponential backoff until the redirect resolves to a Maps place URL.
    final_url = None
    delay = 0.1
    for attempt in range(5):
        try:
            req = urllib.request.Request(maps_url, method="HEAD")
            with urllib.request.urlopen(req, timeout=5) as resp:
                resolved = resp.geturl()
            if "/maps/place/" in resolved:
                final_url = resolved
                break
            app.logger.warning(
                "[Share Target] Attempt %d: resolved to %r (no place path yet)",
                attempt + 1,
                resolved,
            )
        except Exception as e:
            app.logger.warning(
                "[Share Target] Attempt %d failed for %r: %s", attempt + 1, maps_url, e
            )
        if attempt < 4:
            time.sleep(delay)
            delay *= 2

    if not final_url:
        return None

    # Parse /maps/place/NAME+ADDRESS/ from the final URL path
    match = re.search(r"/maps/place/([^/?]+)", final_url)
    if not match:
        return None

    return urllib.parse.unquote_plus(match.group(1))


@app.route("/api/cities")
@login_required
def get_cities():
    db = get_db()
    cur = db.execute(
        'SELECT DISTINCT city FROM restaurants WHERE city IS NOT NULL AND city != "" ORDER BY city ASC'
    )
    cities = [row[0] for row in cur.fetchall()]
    return jsonify(cities)


@app.route("/api/restaurants", methods=["GET", "POST"])
@login_required
def restaurants():
    db = get_db()
    if request.method == "POST":
        data = request.get_json() or {}
        id = data.get("id")
        name = data.get("name")
        dining_options = data.get("diningOptions")
        rating = data.get("rating")
        address = data.get("address")
        city = data.get("city")
        map_uri = data.get("mapUri")
        directions_uri = data.get("directionsUri")
        price_level = data.get("priceLevel")
        notes = data.get("notes")
        dishes = data.get("dishes")
        opening_hours = data.get("openingHours")
        types = data.get("types")
        latitude = data.get("latitude")
        longitude = data.get("longitude")

        # Serialize opening_hours to JSON string if present
        opening_hours_json = None
        if opening_hours:
            opening_hours_json = json.dumps(opening_hours)

        types_json = json.dumps(types) if types is not None else None
        wishlisted = bool(data.get("wishlisted", False))

        if wishlisted == (rating is not None):
            return (
                jsonify(
                    {"error": "exactly one of wishlisted (true) and rating must be set"}
                ),
                400,
            )

        if not wishlisted:
            try:
                rating = int(rating)
            except (ValueError, TypeError):
                return jsonify({"error": "rating must be an integer 1-5"}), 400
            if not (1 <= rating <= 5):
                return jsonify({"error": "rating must be between 1 and 5"}), 400

        if not name or dining_options not in ("dine-in", "delivery", "both"):
            return jsonify({"error": "invalid data"}), 400

        db.execute(
            "INSERT INTO restaurants (id, name, dining_options, rating, wishlisted, address, city, map_uri, directions_uri, price_level, notes, opening_hours, types, latitude, longitude, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)",
            (
                id,
                name,
                dining_options,
                rating,
                wishlisted,
                address,
                city,
                map_uri,
                directions_uri,
                price_level,
                notes,
                opening_hours_json,
                types_json,
                latitude,
                longitude,
            ),
        )

        if dishes and isinstance(dishes, list):
            seen = set()
            for dish in dishes:
                d_name = dish.get("name")
                if d_name:
                    if d_name in seen:
                        return jsonify({"error": f"Duplicate dish: {d_name}"}), 400
                    seen.add(d_name)

            dishes_params = []
            for dish in dishes:
                d_name = dish.get("name")
                d_rating = dish.get("rating")
                d_notes = dish.get("notes")
                try:
                    d_rating = int(d_rating)
                except (ValueError, TypeError):
                    continue

                if d_name and d_rating in (0, 1):
                    dishes_params.append((id, d_name, d_rating, d_notes))

            if dishes_params:
                db.executemany(
                    "INSERT INTO dishes (restaurant_id, name, rating, notes) VALUES (?, ?, ?, ?)",
                    dishes_params,
                )

        db.commit()
        return jsonify(_get_restaurant(db, id)), 201

    cur = db.execute(
        "SELECT id, name, dining_options, rating, wishlisted, address, city, map_uri, directions_uri, price_level, notes, opening_hours, types, latitude, longitude, created_at FROM restaurants ORDER BY created_at DESC"
    )
    restaurants = []
    for r in cur.fetchall():
        restaurants.append(snake_to_camel(parse_restaurant_row(r)))

    cur = db.execute(
        "SELECT rowid, restaurant_id, name, rating, notes FROM dishes ORDER BY rowid"
    )
    dishes_rows = cur.fetchall()

    dishes_map = {}
    for d in dishes_rows:
        rid = d["restaurant_id"]
        dish_dict = {
            "id": d["rowid"],
            "name": d["name"],
            "rating": d["rating"],
            "notes": d["notes"],
        }
        if rid not in dishes_map:
            dishes_map[rid] = []
        dishes_map[rid].append(dish_dict)

    for r in restaurants:
        r["dishes"] = dishes_map.get(r["id"], [])

    return jsonify(restaurants)


def _get_restaurant(db, rest_id):
    cur = db.execute(
        "SELECT id, name, dining_options, rating, wishlisted, address, city, map_uri, directions_uri, price_level, notes, opening_hours, types, latitude, longitude, created_at FROM restaurants WHERE id = ?",
        (rest_id,),
    )
    row = cur.fetchone()
    if row is None:
        return None
    cur2 = db.execute(
        "SELECT rowid, name, rating, notes FROM dishes WHERE restaurant_id = ? ORDER BY rowid",
        (rest_id,),
    )
    restaurant = snake_to_camel(parse_restaurant_row(row))
    restaurant["dishes"] = [
        {
            "id": d["rowid"],
            "name": d["name"],
            "rating": d["rating"],
            "notes": d["notes"],
        }
        for d in cur2.fetchall()
    ]
    return restaurant


@app.route("/api/restaurants/<rest_id>", methods=["GET"])
@login_required
def get_restaurant(rest_id):
    db = get_db()
    data = _get_restaurant(db, rest_id)
    if data is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(data)


@app.route("/api/restaurants/<rest_id>", methods=["PUT"])
@login_required
def update_restaurant(rest_id):
    db = get_db()
    data = request.get_json() or {}

    # Optional fields for partial updates or full refresh
    name = data.get("name")
    address = data.get("address")
    city = data.get("city")
    map_uri = data.get("mapUri")
    directions_uri = data.get("directionsUri")
    price_level = data.get("priceLevel")
    opening_hours = data.get("openingHours")
    types = data.get("types")

    dining_options = data.get("diningOptions")
    rating = data.get("rating")
    notes = data.get("notes")
    wishlisted = data.get("wishlisted")  # None means not provided

    if dining_options is not None and dining_options not in (
        "dine-in",
        "delivery",
        "both",
    ):
        return jsonify({"error": "invalid dining_options"}), 400

    if rating is not None:
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                return jsonify({"error": "rating must be 1-5"}), 400
        except (ValueError, TypeError):
            return jsonify({"error": "rating must be integer"}), 400

    cur = db.execute(
        "SELECT id, dining_options, rating, wishlisted, notes, name, address, city, map_uri, directions_uri, price_level, opening_hours, types, latitude, longitude FROM restaurants WHERE id = ?",
        (rest_id,),
    )
    row = cur.fetchone()
    if row is None:
        return jsonify({"error": "not found"}), 404

    current_data = dict(row)
    current_wishlisted = bool(current_data["wishlisted"])

    new_wishlisted = bool(wishlisted) if wishlisted is not None else current_wishlisted
    new_rating = rating if rating is not None else current_data["rating"]

    if new_wishlisted == (new_rating is not None):
        return (
            jsonify(
                {"error": "exactly one of wishlisted (true) and rating must be set"}
            ),
            400,
        )

    if new_wishlisted and not current_wishlisted:
        return jsonify({"error": "cannot mark a visited restaurant as wishlisted"}), 400

    new_name = name if name is not None else current_data["name"]
    new_type = (
        dining_options if dining_options is not None else current_data["dining_options"]
    )
    new_notes = notes if notes is not None else current_data["notes"]
    new_address = address if address is not None else current_data["address"]
    new_city = city if city is not None else current_data["city"]
    new_map_uri = map_uri if map_uri is not None else current_data["map_uri"]
    new_directions_uri = (
        directions_uri if directions_uri is not None else current_data["directions_uri"]
    )
    new_price_level = (
        price_level if price_level is not None else current_data["price_level"]
    )

    new_opening_hours_json = current_data["opening_hours"]
    if opening_hours is not None:
        new_opening_hours_json = json.dumps(opening_hours)

    new_types_json = current_data["types"]
    if types is not None:
        new_types_json = json.dumps(types)

    new_latitude = data["latitude"] if "latitude" in data else current_data["latitude"]
    new_longitude = (
        data["longitude"] if "longitude" in data else current_data["longitude"]
    )

    marking_as_visited = current_wishlisted and not new_wishlisted

    db.execute(
        """UPDATE restaurants SET
           name = ?, dining_options = ?, rating = ?, wishlisted = ?, notes = ?,
           address = ?, city = ?, map_uri = ?, directions_uri = ?,
           price_level = ?, opening_hours = ?, types = ?, latitude = ?, longitude = ?"""
        + (", created_at = CURRENT_TIMESTAMP" if marking_as_visited else "")
        + " WHERE id = ?",
        (
            new_name,
            new_type,
            new_rating,
            new_wishlisted,
            new_notes,
            new_address,
            new_city,
            new_map_uri,
            new_directions_uri,
            new_price_level,
            new_opening_hours_json,
            new_types_json,
            new_latitude,
            new_longitude,
            rest_id,
        ),
    )

    dishes = data.get("dishes")
    if dishes is not None and isinstance(dishes, list):
        seen = set()
        for dish in dishes:
            d_name = dish.get("name")
            if d_name:
                if d_name in seen:
                    return jsonify({"error": f"Duplicate dish: {d_name}"}), 400
                seen.add(d_name)

        cur = db.execute("SELECT rowid FROM dishes WHERE restaurant_id = ?", (rest_id,))
        existing_ids = set(row["rowid"] for row in cur.fetchall())

        to_insert = []
        to_update = []
        incoming_ids = set()

        for dish in dishes:
            d_name = dish.get("name")
            if not d_name:
                continue

            d_rating = dish.get("rating")
            d_notes = dish.get("notes")
            try:
                d_rating = int(d_rating)
            except (ValueError, TypeError):
                continue

            if d_rating not in (0, 1):
                continue

            d_id = dish.get("id")
            if d_id:
                try:
                    d_id = int(d_id)
                except:
                    d_id = None

            if d_id and d_id in existing_ids:
                incoming_ids.add(d_id)
                to_update.append((d_name, d_rating, d_notes, d_id))
            else:
                to_insert.append((rest_id, d_name, d_rating, d_notes))

        to_delete = [(rowid,) for rowid in existing_ids if rowid not in incoming_ids]

        if to_delete:
            db.executemany("DELETE FROM dishes WHERE rowid = ?", to_delete)
        if to_update:
            db.executemany(
                "UPDATE dishes SET name = ?, rating = ?, notes = ? WHERE rowid = ?",
                to_update,
            )
        if to_insert:
            db.executemany(
                "INSERT INTO dishes (restaurant_id, name, rating, notes) VALUES (?, ?, ?, ?)",
                to_insert,
            )

    db.commit()
    return jsonify(_get_restaurant(db, rest_id)), 200


@app.route("/api/restaurants/<rest_id>", methods=["DELETE"])
@login_required
def delete_restaurant(rest_id):
    db = get_db()
    cur = db.execute("SELECT id FROM restaurants WHERE id = ?", (rest_id,))
    if cur.fetchone() is None:
        return jsonify({"error": rest_id + " not found"}), 404
    db.execute("DELETE FROM restaurants WHERE id = ?", (rest_id,))
    db.commit()
    return jsonify({"status": "deleted"})


_db_dir = os.path.dirname(DATABASE)
if _db_dir:
    os.makedirs(_db_dir, exist_ok=True)
with sqlite3.connect(DATABASE) as _conn:
    app.secret_key = _init_db(_conn)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
