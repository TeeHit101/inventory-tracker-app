from flask import Flask, request, jsonify, render_template
import psycopg2
import redis
import os
import json

template_dir = os.path.abspath('templates')
app = Flask(__name__, template_folder=template_dir)

# Databaskonfiguration (miljövariabler injiceras via ESO)
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST', 'postgres-service'),
        database='inventorydb',
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD')
    )
    return conn

# Redis-konfiguration
cache = redis.Redis(host=os.getenv('REDIS_HOST', 'redis-service'), port=6379, db=0)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/items', methods=['GET'])
def get_items():
    # 1. Kolla Redis-cache
    cached_data = cache.get('inventory_list')
    if cached_data:
        return jsonify({"source": "cache", "items": json.loads(cached_data)})

    # 2. Om tomt, hämta från Postgres
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('SELECT name, quantity FROM items;')
    items = [{"name": row[0], "quantity": row[1]} for row in cur.fetchall()]
    cur.close()
    conn.close()

    # 3. Spara i cache (60 sekunder)
    cache.setex('inventory_list', 60, json.dumps(items))
    return jsonify({"source": "database", "items": items})

@app.route('/items', methods=['POST'])
def add_item():
    data = request.json
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute('INSERT INTO items (name, quantity) VALUES (%s, %s)', (data['name'], data['quantity']))
    conn.commit()
    cur.close()
    conn.close()
    
    # Rensa cache vid uppdatering
    cache.delete('inventory_list')
    return jsonify({"status": "success"}), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)