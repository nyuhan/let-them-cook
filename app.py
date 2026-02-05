from flask import Flask, g, jsonify, request, render_template
import os
import sqlite3
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = os.path.dirname(__file__)
DATABASE = os.environ.get('SQLITE_FILE_PATH') or os.path.join(BASE_DIR, 'instance', 'restaurants.db')

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        os.makedirs(os.path.dirname(DATABASE), exist_ok=True)
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute(
            '''CREATE TABLE IF NOT EXISTS restaurants (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                address TEXT NOT NULL,
                city TEXT NOT NULL,
                map_uri TEXT,
                directions_uri TEXT,
                type TEXT CHECK(type IN ('dine-in','delivery','both')) NOT NULL,
                rating INTEGER CHECK(rating BETWEEN 1 AND 5) NOT NULL,
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP)
            )'''
        )
        
        # Check for price_level column and add if missing
        cur = db.execute("PRAGMA table_info(restaurants)")
        columns = [row['name'] for row in cur.fetchall()]
        if 'price_level' not in columns:
            db.execute('ALTER TABLE restaurants ADD COLUMN price_level INTEGER')
        
        # Check for notes column and add if missing
        if 'notes' not in columns:
            db.execute('ALTER TABLE restaurants ADD COLUMN notes TEXT')

        # Create dishes table
        db.execute(
            '''CREATE TABLE IF NOT EXISTS dishes (
                restaurant_id TEXT NOT NULL,
                name TEXT NOT NULL,
                rating INTEGER CHECK(rating IN (0, 1)) NOT NULL,
                notes TEXT,
                created_at TEXT DEFAULT (CURRENT_TIMESTAMP),
                PRIMARY KEY (restaurant_id, name),
                FOREIGN KEY(restaurant_id) REFERENCES restaurants(id) ON DELETE CASCADE
            )'''
        )

        db.commit()
    return db

app = Flask(__name__, static_folder='static', template_folder='templates')


def snake_to_camel(snake_dict):
    """Convert dictionary keys from snake_case to camelCase"""
    camel_dict = {}
    for key, value in snake_dict.items():
        components = key.split('_')
        camel_key = components[0] + ''.join(x.title() for x in components[1:])
        camel_dict[camel_key] = value
    return camel_dict


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()


@app.route('/')
def index():
    key = os.environ.get('GOOGLE_MAPS_API_KEY')
    return render_template('index.html', google_api_key=key)


@app.route('/api/cities')
def get_cities():
    db = get_db()
    cur = db.execute('SELECT DISTINCT city FROM restaurants WHERE city IS NOT NULL AND city != "" ORDER BY city ASC')
    cities = [row[0] for row in cur.fetchall()]
    return jsonify(cities)


@app.route('/api/restaurants', methods=['GET', 'POST'])
def restaurants():
    db = get_db()
    if request.method == 'POST':
        data = request.get_json() or {}
        id = data.get('id')
        name = data.get('name')
        rtype = data.get('type')
        rating = data.get('rating')
        address = data.get('address')
        city = data.get('city')
        map_uri = data.get('mapUri')
        directions_uri = data.get('directionsUri')
        price_level = data.get('priceLevel')
        notes = data.get('notes')
        dishes = data.get('dishes')
        try:
            rating = int(rating)
        except Exception:
            return jsonify({'error': 'rating must be an integer 1-5'}), 400
        if not name or rtype not in ('dine-in', 'delivery', 'both') or not (1 <= rating <= 5):
            return jsonify({'error': 'invalid data'}), 400
        db.execute(
            'INSERT INTO restaurants (id ,name, type, rating, address, city, map_uri, directions_uri, price_level, notes, created_at) VALUES (?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)',
            (id, name, rtype, rating, address, city, map_uri, directions_uri, price_level, notes),
        )

        if dishes and isinstance(dishes, list):
            dishes_params = []
            for dish in dishes:
                d_name = dish.get('name')
                d_rating = dish.get('rating')
                d_notes = dish.get('notes')
                try:
                    d_rating = int(d_rating)
                except (ValueError, TypeError):
                    continue

                if d_name and d_rating in (0, 1):
                    dishes_params.append((id, d_name, d_rating, d_notes))
            
            if dishes_params:
                db.executemany(
                    'INSERT INTO dishes (restaurant_id, name, rating, notes) VALUES (?, ?, ?, ?)',
                    dishes_params
                )

        db.commit()
        return jsonify({'status': 'ok'}), 201

    cur = db.execute('SELECT id, name, type, rating, address, city, map_uri, directions_uri, price_level, notes, created_at FROM restaurants ORDER BY id DESC')
    restaurants = [snake_to_camel(dict(r)) for r in cur.fetchall()]

    cur = db.execute('SELECT restaurant_id, name, rating, notes FROM dishes')
    dishes_rows = cur.fetchall()

    dishes_map = {}
    for d in dishes_rows:
        rid = d['restaurant_id']
        dish_dict = {'name': d['name'], 'rating': d['rating'], 'notes': d['notes']}
        if rid not in dishes_map:
            dishes_map[rid] = []
        dishes_map[rid].append(dish_dict)

    for r in restaurants:
        r['dishes'] = dishes_map.get(r['id'], [])

    return jsonify(restaurants)


@app.route('/api/restaurants/<rest_id>', methods=['PUT'])
def update_restaurant(rest_id):
    db = get_db()
    data = request.get_json() or {}
    id = rest_id
    rtype = data.get('type')
    rating = data.get('rating')
    try:
        rating = int(rating)
    except Exception:
        return jsonify({'error': 'rating must be an integer 1-5'}), 400
    if rtype not in ('dine-in', 'delivery', 'both') or not (1 <= rating <= 5):
        return jsonify({'error': 'invalid data'}), 400
    cur = db.execute('SELECT id FROM restaurants WHERE id = ?', (rest_id,))
    if cur.fetchone() is None:
        return jsonify({'error': 'not found'}), 404
    notes = data.get('notes')
    db.execute(
        'UPDATE restaurants SET type = ?, rating = ?, notes = ? WHERE id = ?',
        (rtype, rating, notes, rest_id),
    )

    dishes = data.get('dishes')
    if dishes is not None and isinstance(dishes, list):
        cur = db.execute('SELECT name, rating, notes FROM dishes WHERE restaurant_id = ?', (rest_id,))
        existing_dishes = {row['name']: {'rating': row['rating'], 'notes': row['notes']} for row in cur.fetchall()}

        to_insert = []
        to_update = []
        incoming_names = set()

        for dish in dishes:
            d_name = dish.get('name')
            if not d_name:
                continue
            
            d_rating = dish.get('rating')
            d_notes = dish.get('notes')
            try:
                d_rating = int(d_rating)
            except (ValueError, TypeError):
                continue
            
            if d_rating not in (0, 1):
                continue

            incoming_names.add(d_name)

            if d_name in existing_dishes:
                current = existing_dishes[d_name]
                if current['rating'] != d_rating or current['notes'] != d_notes:
                    to_update.append((d_rating, d_notes, rest_id, d_name))
            else:
                to_insert.append((rest_id, d_name, d_rating, d_notes))
        
        to_delete = [(rest_id, name) for name in existing_dishes if name not in incoming_names]

        if to_insert:
            db.executemany('INSERT INTO dishes (restaurant_id, name, rating, notes) VALUES (?, ?, ?, ?)', to_insert)
        if to_update:
            db.executemany('UPDATE dishes SET rating = ?, notes = ? WHERE restaurant_id = ? AND name = ?', to_update)
        if to_delete:
            db.executemany('DELETE FROM dishes WHERE restaurant_id = ? AND name = ?', to_delete)

    db.commit()
    return jsonify({'status': 'ok'}), 200


@app.route('/api/restaurants/<rest_id>', methods=['DELETE'])
def delete_restaurant(rest_id):
    db = get_db()
    cur = db.execute('SELECT id FROM restaurants WHERE id = ?', (rest_id,))
    if cur.fetchone() is None:
        return jsonify({'error': rest_id + ' not found'}), 404
    db.execute('DELETE FROM restaurants WHERE id = ?', (rest_id,))
    db.commit()
    return jsonify({'status': 'deleted'})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
