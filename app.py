from flask import Flask, request, jsonify, render_template
import psycopg2
import redis
import os
import json
import time

template_dir = os.path.abspath('templates')
app = Flask(__name__, template_folder=template_dir)

# --- KONFIGURATION ---
DB_CONFIG = {
    "host": os.getenv('DB_HOST', 'postgres-service'),
    "database": os.getenv('DB_NAME', 'inventory_db'),
    "user": os.getenv('DB_USER', 'inventory_user'),
    "password": os.getenv('DB_PASSWORD')
}

REDIS_CONFIG = {
    "host": os.getenv('REDIS_HOST', 'redis-service'),
    "port": 6379,
    "db": 0
}

cache = redis.Redis(**REDIS_CONFIG)

def get_db_connection():
    return psycopg2.connect(**DB_CONFIG)

# --- AUTOMATISK INITIERING (Viktigt för Tofu Destroy/Apply) ---
def init_db():
    """Väntar på Postgres och skapar tabellen om den saknas"""
    print("🚀 Inleder databasinitiering...")
    retries = 10
    while retries > 0:
        try:
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute('''
                CREATE TABLE IF NOT EXISTS items (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    quantity INTEGER NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            conn.commit()
            cur.close()
            conn.close()
            print("✅ Databas och tabellen 'items' är redo!")
            return
        except Exception as e:
            print(f"⚠️ Databasen är inte redo än ({e}). Testar igen om 5s... ({retries} försök kvar)")
            retries -= 1
            time.sleep(5)
    print("❌ Kunde inte ansluta till databasen efter flera försök.")

# --- API ROUTES (CRUD) ---

@app.route('/')
def index():
    return render_template('index.html')

# 1. READ (Hämta alla artiklar med Cache)
@app.route('/items', methods=['GET'])
def get_items():
    cached_data = cache.get('inventory_list')
    if cached_data:
        print("⚡ Hämtar från Redis-cache")
        return jsonify({"source": "cache", "items": json.loads(cached_data)})

    print("🐘 Hämtar från Postgres-databas")
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, quantity FROM items ORDER BY name ASC;')
    items = [{"name": row[0], "quantity": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()

    cache.setex('inventory_list', 60, json.dumps(items))
    return jsonify({"source": "database", "items": items})

# 2. CREATE (Lägg till ny artikel)
@app.route('/items', methods=['POST'])
def add_item():
    data = request.json
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('INSERT INTO items (name, quantity) VALUES (%s, %s)', (data['name'], data['quantity']))
        conn.commit()
        cur.close()
        conn.close()
        cache.delete('inventory_list') # Invalidera cache
        return jsonify({"status": "created"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

# 3. UPDATE (Ändra antal)
@app.route('/items/<string:name>', methods=['PUT'])
def update_item(name):
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('UPDATE items SET quantity = %s WHERE name = %s', (data['quantity'], name))
    conn.commit()
    rows = cur.rowcount
    cur.close()
    conn.close()
    
    if rows > 0:
        cache.delete('inventory_list')
        return jsonify({"status": "updated"})
    return jsonify({"error": "Item not found"}), 404

# 4. DELETE (Ta bort artikel)
@app.route('/items/<string:name>', methods=['DELETE'])
def delete_item(name):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('DELETE FROM items WHERE name = %s', (name,))
    conn.commit()
    rows = cur.rowcount
    cur.close()
    conn.close()
    
    if rows > 0:
        cache.delete('inventory_list')
        return jsonify({"status": "deleted"})
    return jsonify({"error": "Item not found"}), 404

if __name__ == '__main__':
    init_db() # Körs alltid innan Flask startar
    app.run(host='0.0.0.0', port=5000)