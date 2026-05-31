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

cur.execute("SELECT COUNT(*) FROM realtime_positions;")
count = cur.fetchone()[0]

print("Nombre total de positions :", count)

cur.execute("""
SELECT truck_id, latitude, longitude, progress, estimated_delay_minutes, rain, route_risk_score, status, event_time
FROM realtime_positions
ORDER BY event_time DESC
LIMIT 10;
""")

rows = cur.fetchall()

for row in rows:
    print(row)

cur.close()
conn.close()