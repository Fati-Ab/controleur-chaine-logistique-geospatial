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

cur.execute("SELECT COUNT(*) FROM optimized_routes;")
print("Nombre de routes optimisées :", cur.fetchone()[0])

cur.execute("""
SELECT
    ROUND(SUM(distance_before_km)::numeric, 2),
    ROUND(SUM(distance_after_km)::numeric, 2),
    ROUND(SUM(savings_km)::numeric, 2),
    ROUND(SUM(savings_cost)::numeric, 2)
FROM optimized_routes;
""")

print("\nRésumé global :")
print(cur.fetchone())

cur.execute("""
SELECT
    trip_id,
    taxi_id,
    distance_before_km,
    distance_after_km,
    savings_km,
    savings_cost,
    risk_level
FROM optimized_routes
ORDER BY savings_cost DESC
LIMIT 10;
""")

print("\nTop 10 économies :")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()