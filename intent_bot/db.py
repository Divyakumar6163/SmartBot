import psycopg2

def get_connection():
    return psycopg2.connect(
        host="localhost",
        database="voicebot",
        user="voicebot_user",
        password="12345",
        port=5432
    )

def fetch_one(query, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    row = cur.fetchone()
    conn.close()
    return row

def fetch_all(query, params=()):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()
    return rows
