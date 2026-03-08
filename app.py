from flask import Flask, g, jsonify, request, render_template
import os
import sqlite3
import json
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
                dining_options TEXT CHECK(dining_options IN ('dine-in','delivery','both')) NOT NULL,
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
        
        # Check for opening_hours column and add if missing
        if 'opening_hours' not in columns:
            db.execute('ALTER TABLE restaurants ADD COLUMN opening_hours TEXT')

        # Rename type column to dining_options if needed
        if 'type' in columns and 'dining_options' not in columns:
            db.execute('ALTER TABLE restaurants RENAME COLUMN type TO dining_options')

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


def parse_restaurant_row(row):
    """Convert a DB row to a dict with opening_hours deserialized."""
    d = dict(row)
    if d.get('opening_hours'):
        try:
            d['opening_hours'] = json.loads(d['opening_hours'])
        except (json.JSONDecodeError, TypeError):
            d['opening_hours'] = None
    return d


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
        rtype = data.get('diningOptions')
        rating = data.get('rating')
        address = data.get('address')
        city = data.get('city')
        map_uri = data.get('mapUri')
        directions_uri = data.get('directionsUri')
        price_level = data.get('priceLevel')
        notes = data.get('notes')
        dishes = data.get('dishes')
        opening_hours = data.get('openingHours')
        
        # Serialize opening_hours to JSON string if present
        opening_hours_json = None
        if opening_hours:
            opening_hours_json = json.dumps(opening_hours)

        try:
            rating = int(rating)
        except Exception:
            return jsonify({'error': 'rating must be an integer 1-5'}), 400
        if not name or rtype not in ('dine-in', 'delivery', 'both') or not (1 <= rating <= 5):
            return jsonify({'error': 'invalid data'}), 400
        db.execute(
            'INSERT INTO restaurants (id ,name, dining_options, rating, address, city, map_uri, directions_uri, price_level, notes, opening_hours, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?, CURRENT_TIMESTAMP)',
            (id, name, rtype, rating, address, city, map_uri, directions_uri, price_level, notes, opening_hours_json),
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

    cur = db.execute('SELECT id, name, dining_options, rating, address, city, map_uri, directions_uri, price_level, notes, opening_hours, created_at FROM restaurants ORDER BY id DESC')
    restaurants = []
    for r in cur.fetchall():
        restaurants.append(snake_to_camel(parse_restaurant_row(r)))

    cur = db.execute('SELECT rowid, restaurant_id, name, rating, notes FROM dishes ORDER BY rowid')
    dishes_rows = cur.fetchall()

    dishes_map = {}
    for d in dishes_rows:
        rid = d['restaurant_id']
        dish_dict = {'id': d['rowid'], 'name': d['name'], 'rating': d['rating'], 'notes': d['notes']}
        if rid not in dishes_map:
            dishes_map[rid] = []
        dishes_map[rid].append(dish_dict)

    for r in restaurants:
        r['dishes'] = dishes_map.get(r['id'], [])

    return jsonify(restaurants)


@app.route('/api/restaurants/<rest_id>', methods=['GET'])
def get_restaurant(rest_id):
    db = get_db()
    cur = db.execute('SELECT * FROM restaurants WHERE id = ?', (rest_id,))
    row = cur.fetchone()
    if row is None:
        return jsonify({'error': 'not found'}), 404
    return jsonify(snake_to_camel(parse_restaurant_row(row)))


@app.route('/api/restaurants/<rest_id>', methods=['PUT'])
def update_restaurant(rest_id):
    db = get_db()
    data = request.get_json() or {}
    
    # Optional fields for partial updates or full refresh
    name = data.get('name')
    address = data.get('address')
    city = data.get('city')
    map_uri = data.get('mapUri')
    directions_uri = data.get('directionsUri')
    price_level = data.get('priceLevel')
    opening_hours = data.get('openingHours')

    rtype = data.get('diningOptions')
    rating = data.get('rating')
    notes = data.get('notes')

    # Basic validations if we are updating these fields
    if rating is not None:
        try:
            rating = int(rating)
            if not (1 <= rating <= 5):
                 return jsonify({'error': 'rating must be 1-5'}), 400
        except:
             return jsonify({'error': 'rating must be integer'}), 400

    if rtype is not None and rtype not in ('dine-in', 'delivery', 'both'):
        return jsonify({'error': 'invalid type'}), 400

    cur = db.execute('SELECT id, dining_options, rating, notes, name, address, city, map_uri, directions_uri, price_level, opening_hours FROM restaurants WHERE id = ?', (rest_id,))
    row = cur.fetchone()
    if row is None:
        return jsonify({'error': 'not found'}), 404
    
    # Use existing values if not provided (though for refresh we likely provide all)
    current_data = dict(row)
    
    new_name = name if name is not None else current_data['name']
    new_type = rtype if rtype is not None else current_data['dining_options']
    new_rating = rating if rating is not None else current_data['rating']
    new_notes = notes if notes is not None else current_data['notes']
    new_address = address if address is not None else current_data['address']
    new_city = city if city is not None else current_data['city']
    new_map_uri = map_uri if map_uri is not None else current_data['map_uri']
    new_directions_uri = directions_uri if directions_uri is not None else current_data['directions_uri']
    new_price_level = price_level if price_level is not None else current_data['price_level']
    
    new_opening_hours_json = current_data['opening_hours']
    if opening_hours is not None:
        new_opening_hours_json = json.dumps(opening_hours)

    db.execute(
        '''UPDATE restaurants SET 
           name = ?, dining_options = ?, rating = ?, notes = ?, 
           address = ?, city = ?, map_uri = ?, directions_uri = ?, 
           price_level = ?, opening_hours = ? 
           WHERE id = ?''',
        (new_name, new_type, new_rating, new_notes, 
         new_address, new_city, new_map_uri, new_directions_uri, 
         new_price_level, new_opening_hours_json, rest_id),
    )

    dishes = data.get('dishes')
    if dishes is not None and isinstance(dishes, list):
        cur = db.execute('SELECT rowid FROM dishes WHERE restaurant_id = ?', (rest_id,))
        existing_ids = set(row['rowid'] for row in cur.fetchall())

        to_insert = []
        to_update = []
        incoming_ids = set()

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
            
            d_id = dish.get('id')
            if d_id:
                try: d_id = int(d_id)
                except: d_id = None
                
            if d_id and d_id in existing_ids:
                incoming_ids.add(d_id)
                to_update.append((d_name, d_rating, d_notes, d_id))
            else:
                to_insert.append((rest_id, d_name, d_rating, d_notes))
        
        to_delete = [(rowid,) for rowid in existing_ids if rowid not in incoming_ids]

        if to_delete:
            db.executemany('DELETE FROM dishes WHERE rowid = ?', to_delete)
        if to_update:
            db.executemany('UPDATE dishes SET name = ?, rating = ?, notes = ? WHERE rowid = ?', to_update)
        if to_insert:
            db.executemany('INSERT INTO dishes (restaurant_id, name, rating, notes) VALUES (?, ?, ?, ?)', to_insert)

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
