from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from werkzeug.security import generate_password_hash, check_password_hash
import psycopg2
import redis
import os
import json
import time

template_dir = os.path.abspath('templates')
app = Flask(__name__, template_folder=template_dir)

# 🔐 Secret key for sessions
app.secret_key = os.getenv("SECRET_KEY", "change-this-in-production")

# --- DATABASE CONFIG ---
DB_CONFIG = {
    "host": os.getenv('DB_HOST', 'postgres-service'),
    "database": os.getenv('DB_NAME', 'inventory_db'),
    "user": os.getenv('DB_USER', 'inventory_user'),
    "password": os.getenv('DB_PASSWORD')
}

# --- REDIS CONFIG ---
REDIS_CONFIG = {
    "host": os.getenv('REDIS_HOST', 'redis-service'),
    "port": 6379,
    "db": 0
}

cache = redis.Redis(**REDIS_CONFIG)

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- INIT DATABASE ---
def init_db():
    print("🚀 Initializing database...")
    retries = 10
    while retries > 0:
        try:
            conn = get_db_connection()
            cur = conn.cursor()

            # Inventory table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    quantity INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            # Users table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')

            conn.commit()
            cur.close()
            conn.close()
            print("✅ Database ready!")
            return
        except Exception as e:
            print(f"⚠️ DB not ready ({e}), retrying...")
            retries -= 1
            time.sleep(5)

# --- AUTH HELPERS ---
def require_login():
    if 'user' not in session:
        return jsonify({"error": "Unauthorized"}), 401

# --- ROUTES ---

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/login', methods=['GET'])
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT password_hash FROM users WHERE username = %s', (data['username'],))
    row = cur.fetchone()
    cur.close()
    conn.close()

    if row and check_password_hash(row[0], data['password']):
        session['user'] = data['username']
        return jsonify({"status": "logged_in"})
    return jsonify({"error": "Invalid credentials"}), 401

@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user', None)
    return jsonify({"status": "logged_out"})

# --- REGISTER (use once to create user) ---
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    password_hash = generate_password_hash(data['password'])

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO users (username, password_hash) VALUES (%s, %s)',
            (data['username'], password_hash)
        )
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({"status": "user created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# --- INVENTORY API ---

@app.route('/items', methods=['GET'])
def get_items():
    auth = require_login()
    if auth: return auth

    cached = cache.get('inventory_list')
    if cached:
        return jsonify({"source": "cache", "items": json.loads(cached)})

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, quantity FROM items ORDER BY name ASC;')
    items = [{"name": r[0], "quantity": r[1]} for r in cur.fetchall()]
    cur.close()
    conn.close()

    cache.setex('inventory_list', 60, json.dumps(items))
    return jsonify({"source": "database", "items": items})

@app.route('/items', methods=['POST'])
def add_item():
    auth = require_login()
    if auth: return auth

    data = request.json

    if not data.get("name") or not isinstance(data.get("quantity"), int):
        return jsonify({"error": "Invalid input"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO items (name, quantity) VALUES (%s, %s)', (data['name'], data['quantity']))
        conn.commit()
        cur.close()
        conn.close()
        cache.delete('inventory_list')
        return jsonify({"status": "created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.route('/items/<string:name>', methods=['PUT'])
def update_item(name):
    auth = require_login()
    if auth: return auth

    data = request.json

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE items SET quantity = %s WHERE name = %s', (data['quantity'], name))
    conn.commit()
    rows = cur.rowcount
    cur.close()
    conn.close()

    if rows:
        cache.delete('inventory_list')
        return jsonify({"status": "updated"})
    return jsonify({"error": "Not found"}), 404

@app.route('/items/<string:name>', methods=['DELETE'])
def delete_item(name):
    auth = require_login()
    if auth: return auth

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM items WHERE name = %s', (name,))
    conn.commit()
    rows = cur.rowcount
    cur.close()
    conn.close()

    if rows:
        cache.delete('inventory_list')
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Not found"}), 404

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=5000)
