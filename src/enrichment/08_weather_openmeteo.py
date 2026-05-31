from datetime import timedelta

import pandas as pd
import psycopg2
import requests
from psycopg2.extras import execute_batch

from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


PORTO_LAT = 41.1579
PORTO_LON = -8.6291


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def get_trip_date_range(conn):
    query = """
    SELECT
        MIN(start_time)::date AS start_date,
        MAX(start_time)::date AS end_date
    FROM trips;
    """

    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()

    start_date, end_date = row

    if start_date is None or end_date is None:
        raise ValueError("Aucune date trouvée dans la table trips.")

    return start_date, end_date


def fetch_openmeteo_weather(start_date, end_date):
    """
    Récupère météo historique Open-Meteo pour Porto.
    """

    url = "https://archive-api.open-meteo.com/v1/archive"

    params = {
        "latitude": PORTO_LAT,
        "longitude": PORTO_LON,
        "start_date": str(start_date),
        "end_date": str(end_date),
        "hourly": [
            "temperature_2m",
            "relative_humidity_2m",
            "precipitation",
            "rain",
            "wind_speed_10m"
        ],
        "timezone": "Europe/Lisbon"
    }

    print("Appel Open-Meteo...")
    print("Période :", start_date, "→", end_date)

    response = requests.get(url, params=params, timeout=60)
    response.raise_for_status()

    data = response.json()

    hourly = data.get("hourly", {})

    df = pd.DataFrame({
        "weather_time": hourly.get("time", []),
        "temperature_2m": hourly.get("temperature_2m", []),
        "relative_humidity_2m": hourly.get("relative_humidity_2m", []),
        "precipitation": hourly.get("precipitation", []),
        "rain": hourly.get("rain", []),
        "wind_speed_10m": hourly.get("wind_speed_10m", [])
    })

    df["weather_time"] = pd.to_datetime(df["weather_time"])

    return df


def create_weather_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS weather_hourly (
        id SERIAL PRIMARY KEY,
        weather_time TIMESTAMP UNIQUE,
        temperature_2m DOUBLE PRECISION,
        relative_humidity_2m DOUBLE PRECISION,
        precipitation DOUBLE PRECISION,
        rain DOUBLE PRECISION,
        wind_speed_10m DOUBLE PRECISION,
        city VARCHAR(100) DEFAULT 'Porto'
    );

    CREATE INDEX IF NOT EXISTS idx_weather_hourly_time
    ON weather_hourly(weather_time);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def clear_weather_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE weather_hourly RESTART IDENTITY;")
        conn.commit()


def insert_weather(conn, df):
    query = """
    INSERT INTO weather_hourly (
        weather_time,
        temperature_2m,
        relative_humidity_2m,
        precipitation,
        rain,
        wind_speed_10m
    )
    VALUES (
        %(weather_time)s,
        %(temperature_2m)s,
        %(relative_humidity_2m)s,
        %(precipitation)s,
        %(rain)s,
        %(wind_speed_10m)s
    )
    ON CONFLICT (weather_time) DO NOTHING;
    """

    rows = df.to_dict(orient="records")

    with conn.cursor() as cur:
        execute_batch(cur, query, rows, page_size=500)
        conn.commit()


def main():
    conn = connect_db()

    print("Création table weather_hourly...")
    create_weather_table(conn)

    start_date, end_date = get_trip_date_range(conn)

    # Petite marge de sécurité
    start_date = start_date - timedelta(days=1)
    end_date = end_date + timedelta(days=1)

    df_weather = fetch_openmeteo_weather(start_date, end_date)

    print("Lignes météo récupérées :", len(df_weather))

    if df_weather.empty:
        print("Aucune donnée météo récupérée.")
        conn.close()
        return

    print("Nettoyage ancienne météo...")
    clear_weather_table(conn)

    print("Insertion météo dans PostGIS...")
    insert_weather(conn, df_weather)

    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM weather_hourly;")
        count = cur.fetchone()[0]

    conn.close()

    print("Météo terminée avec succès.")
    print("Lignes insérées dans weather_hourly :", count)


if __name__ == "__main__":
    main()