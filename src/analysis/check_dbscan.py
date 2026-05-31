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

cur.execute("SELECT COUNT(*) FROM dbscan_clusters;")
print("Nombre total de points DBSCAN :", cur.fetchone()[0])

cur.execute("""
SELECT COUNT(DISTINCT cluster_id)
FROM dbscan_clusters
WHERE cluster_id <> -1;
""")
print("Nombre de clusters :", cur.fetchone()[0])

cur.execute("""
SELECT cluster_id, COUNT(*) AS nb_points
FROM dbscan_clusters
WHERE cluster_id <> -1
GROUP BY cluster_id
ORDER BY nb_points DESC
LIMIT 10;
""")

print("\nTop 10 clusters :")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()