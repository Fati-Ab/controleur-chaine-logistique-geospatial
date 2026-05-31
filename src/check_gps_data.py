import psycopg2
from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM trips;")
print("Nombre de trajets :", cur.fetchone()[0])

cur.execute("SELECT COUNT(*) FROM gps_positions;")
print("Nombre de positions GPS :", cur.fetchone()[0])

cur.execute("SELECT COUNT(DISTINCT taxi_id) FROM gps_positions;")
print("Nombre de taxis différents :", cur.fetchone()[0])

cur.execute("""
SELECT taxi_id, COUNT(*) AS nb_positions
FROM gps_positions
GROUP BY taxi_id
ORDER BY nb_positions DESC
LIMIT 10;
""")

print("\nTop 10 taxis :")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()