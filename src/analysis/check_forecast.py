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

cur.execute("SELECT COUNT(*) FROM forecast_delays;")
print("Nombre de prévisions :", cur.fetchone()[0])

cur.execute("""
SELECT forecast_time, predicted_delay, lower_bound, upper_bound, model_name
FROM forecast_delays
ORDER BY forecast_time
LIMIT 10;
""")

print("\nPremières prévisions :")
for row in cur.fetchall():
    print(row)

cur.close()
conn.close()