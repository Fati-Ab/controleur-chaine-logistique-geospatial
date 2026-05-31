import psycopg2
from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM weather_hourly;")
print("Nombre de lignes météo :", cur.fetchone()[0])

cur.execute("""
SELECT weather_time, temperature_2m, rain, wind_speed_10m, relative_humidity_2m
FROM weather_hourly
ORDER BY weather_time
LIMIT 10;
""")

print("\nPremières lignes météo :")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()