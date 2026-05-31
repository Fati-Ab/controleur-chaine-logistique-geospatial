import psycopg2
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

    cur = conn.cursor()
    cur.execute("SELECT PostGIS_Version();")
    version = cur.fetchone()[0]

    print("Connexion PostgreSQL/PostGIS OK")
    print("Version PostGIS :", version)

    cur.close()
    conn.close()

except Exception as e:
    print("Erreur de connexion :", e)