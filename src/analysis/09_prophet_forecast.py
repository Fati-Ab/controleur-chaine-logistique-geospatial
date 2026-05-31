from datetime import timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


FORECAST_HOURS = 24


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def create_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS forecast_delays (
        id SERIAL PRIMARY KEY,
        forecast_time TIMESTAMP,
        predicted_delay DOUBLE PRECISION,
        lower_bound DOUBLE PRECISION,
        upper_bound DOUBLE PRECISION,
        model_name VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_forecast_delays_time
    ON forecast_delays(forecast_time);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def clear_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE forecast_delays RESTART IDENTITY;")
        conn.commit()


def build_hourly_delay_series(conn):
    """
    Construit une série temporelle des retards moyens par heure.
    On utilise start_time depuis trips et estimated_delay_minutes depuis route_scores.
    """
    query = """
    SELECT
        DATE_TRUNC('hour', t.start_time) AS ds,
        AVG(rs.estimated_delay_minutes) AS y
    FROM route_scores rs
    JOIN trips t ON t.trip_id = rs.trip_id
    GROUP BY DATE_TRUNC('hour', t.start_time)
    ORDER BY ds;
    """

    df = pd.read_sql(query, conn)
    return df


def simple_prophet_like_forecast(df):
    """
    Prévision légère de type Prophet-like :
    - moyenne mobile des 24 dernières heures ;
    - correction heures de pointe ;
    - intervalle lower/upper basé sur l'écart-type.

    Cette version évite les problèmes d'installation de prophet
    tout en gardant une logique de prévision temporelle.
    """
    df = df.copy()

    df["ds"] = pd.to_datetime(df["ds"])
    df["y"] = pd.to_numeric(df["y"], errors="coerce")

    df = df.dropna()

    if df.empty:
        raise ValueError("Aucune donnée valide pour créer la prévision.")

    last_time = df["ds"].max()

    rolling_mean = df["y"].tail(24).mean()
    global_std = df["y"].std()

    if pd.isna(global_std) or global_std == 0:
        global_std = 1.0

    forecast_rows = []

    for i in range(1, FORECAST_HOURS + 1):
        forecast_time = last_time + timedelta(hours=i)

        hour_factor = 1.0

        # Heures de pointe approximatives
        if forecast_time.hour in [8, 9, 17, 18, 19]:
            hour_factor = 1.25

        # Nuit : circulation plus faible
        elif forecast_time.hour in [0, 1, 2, 3, 4, 5]:
            hour_factor = 0.75

        predicted_delay = rolling_mean * hour_factor

        lower_bound = max(predicted_delay - global_std, 0)
        upper_bound = predicted_delay + global_std

        forecast_rows.append({
            "forecast_time": forecast_time,
            "predicted_delay": round(float(predicted_delay), 2),
            "lower_bound": round(float(lower_bound), 2),
            "upper_bound": round(float(upper_bound), 2),
            "model_name": "Prophet-like moving average"
        })

    return forecast_rows


def insert_forecast(conn, rows):
    query = """
    INSERT INTO forecast_delays (
        forecast_time,
        predicted_delay,
        lower_bound,
        upper_bound,
        model_name
    )
    VALUES (
        %(forecast_time)s,
        %(predicted_delay)s,
        %(lower_bound)s,
        %(upper_bound)s,
        %(model_name)s
    );
    """

    with conn.cursor() as cur:
        execute_batch(cur, query, rows, page_size=500)
        conn.commit()


def main():
    conn = connect_db()

    print("Création table forecast_delays...")
    create_table(conn)

    print("Nettoyage ancienne prévision...")
    clear_table(conn)

    print("Chargement série temporelle des retards...")
    df = build_hourly_delay_series(conn)

    print("Points temporels disponibles :", len(df))

    if df.empty:
        print("Aucune donnée disponible.")
        print("Lance d'abord : python -m src.analysis.06_risk_scoring")
        conn.close()
        return

    print("Calcul prévision des retards...")
    rows = simple_prophet_like_forecast(df)

    print("Insertion forecast dans PostGIS...")
    insert_forecast(conn, rows)

    print("\nPrévisions générées :")
    for row in rows[:10]:
        print(row)

    conn.close()

    print("\nPrévision terminée avec succès.")
    print("Table remplie : forecast_delays")


if __name__ == "__main__":
    main()