import psycopg2
from psycopg2.extras import execute_batch

from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


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
    CREATE TABLE IF NOT EXISTS route_scores (
        id SERIAL PRIMARY KEY,
        trip_id VARCHAR(100),
        taxi_id VARCHAR(50),
        distance_km DOUBLE PRECISION,
        duration_min DOUBLE PRECISION,
        estimated_delay_minutes DOUBLE PRECISION,
        rain_mm DOUBLE PRECISION,
        wind_speed_kmh DOUBLE PRECISION,
        temperature_2m DOUBLE PRECISION,
        humidity DOUBLE PRECISION,
        congestion_flag INTEGER,
        risk_score DOUBLE PRECISION,
        risk_level VARCHAR(30),
        created_at TIMESTAMP DEFAULT NOW()
    );

    ALTER TABLE route_scores
    ADD COLUMN IF NOT EXISTS temperature_2m DOUBLE PRECISION;

    ALTER TABLE route_scores
    ADD COLUMN IF NOT EXISTS humidity DOUBLE PRECISION;

    CREATE INDEX IF NOT EXISTS idx_route_scores_trip_id
    ON route_scores(trip_id);

    CREATE INDEX IF NOT EXISTS idx_route_scores_taxi_id
    ON route_scores(taxi_id);

    CREATE INDEX IF NOT EXISTS idx_route_scores_risk_level
    ON route_scores(risk_level);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def clear_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE route_scores RESTART IDENTITY;")
        conn.commit()


def load_trips_with_weather(conn):
    """
    Pour chaque trajet, on récupère la météo horaire la plus proche.
    DATE_TRUNC('hour', t.start_time) permet de joindre le trajet avec weather_hourly.
    """
    query = """
    SELECT
        t.trip_id,
        t.taxi_id,
        t.distance_km,
        t.duration_min,
        COALESCE(w.rain, 0) AS rain_mm,
        COALESCE(w.wind_speed_10m, 0) AS wind_speed_kmh,
        COALESCE(w.temperature_2m, 0) AS temperature_2m,
        COALESCE(w.relative_humidity_2m, 0) AS humidity,
        CASE
            WHEN EXISTS (
                SELECT 1
                FROM dbscan_clusters dc
                WHERE dc.trip_id = t.trip_id
                  AND dc.cluster_id <> -1
                LIMIT 1
            )
            THEN 1
            ELSE 0
        END AS congestion_flag
    FROM trips t
    LEFT JOIN weather_hourly w
        ON DATE_TRUNC('hour', t.start_time) = w.weather_time
    LIMIT 5000;
    """

    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def risk_level(score):
    if score < 10:
        return "LOW"
    if score < 25:
        return "MEDIUM"
    if score < 50:
        return "HIGH"
    return "CRITICAL"


def compute_scores(rows):
    results = []

    for row in rows:
        (
            trip_id,
            taxi_id,
            distance_km,
            duration_min,
            rain_mm,
            wind_speed_kmh,
            temperature_2m,
            humidity,
            congestion_flag
        ) = row

        distance_km = float(distance_km or 0)
        duration_min = float(duration_min or 0)
        rain_mm = float(rain_mm or 0)
        wind_speed_kmh = float(wind_speed_kmh or 0)
        temperature_2m = float(temperature_2m or 0)
        humidity = float(humidity or 0)
        congestion_flag = int(congestion_flag or 0)

        # Durée normale approximative : 3 min par km
        normal_duration = max(distance_km * 3, 1)

        estimated_delay = max(duration_min - normal_duration, 0)

        # Impact météo réel
        estimated_delay += rain_mm * 0.5
        estimated_delay += wind_speed_kmh * 0.05

        # Impact congestion DBSCAN
        estimated_delay += congestion_flag * 5

        estimated_delay = round(estimated_delay, 2)

        risk_score = (
            estimated_delay * 1.0
            + rain_mm * 2.0
            + wind_speed_kmh / 10.0
            + congestion_flag * 20.0
        )

        risk_score = round(risk_score, 2)
        level = risk_level(risk_score)

        results.append({
            "trip_id": str(trip_id),
            "taxi_id": str(taxi_id),
            "distance_km": distance_km,
            "duration_min": duration_min,
            "estimated_delay_minutes": estimated_delay,
            "rain_mm": rain_mm,
            "wind_speed_kmh": wind_speed_kmh,
            "temperature_2m": temperature_2m,
            "humidity": humidity,
            "congestion_flag": congestion_flag,
            "risk_score": risk_score,
            "risk_level": level
        })

    return results


def insert_scores(conn, rows):
    query = """
    INSERT INTO route_scores (
        trip_id,
        taxi_id,
        distance_km,
        duration_min,
        estimated_delay_minutes,
        rain_mm,
        wind_speed_kmh,
        temperature_2m,
        humidity,
        congestion_flag,
        risk_score,
        risk_level
    )
    VALUES (
        %(trip_id)s,
        %(taxi_id)s,
        %(distance_km)s,
        %(duration_min)s,
        %(estimated_delay_minutes)s,
        %(rain_mm)s,
        %(wind_speed_kmh)s,
        %(temperature_2m)s,
        %(humidity)s,
        %(congestion_flag)s,
        %(risk_score)s,
        %(risk_level)s
    );
    """

    with conn.cursor() as cur:
        execute_batch(cur, query, rows, page_size=1000)
        conn.commit()


def main():
    conn = connect_db()

    print("Création/vérification table route_scores...")
    create_table(conn)

    print("Nettoyage ancienne table route_scores...")
    clear_table(conn)

    print("Chargement des trajets + météo réelle Open-Meteo...")
    rows = load_trips_with_weather(conn)

    print("Trajets chargés :", len(rows))

    if not rows:
        print("Aucun trajet trouvé.")
        conn.close()
        return

    print("Calcul des scores de risque avec météo réelle...")
    scores = compute_scores(rows)

    print("Insertion dans PostGIS...")
    insert_scores(conn, scores)

    with conn.cursor() as cur:
        cur.execute("""
            SELECT
                risk_level,
                COUNT(*),
                ROUND(AVG(risk_score)::numeric, 2),
                ROUND(AVG(rain_mm)::numeric, 2),
                ROUND(AVG(wind_speed_kmh)::numeric, 2)
            FROM route_scores
            GROUP BY risk_level
            ORDER BY
                CASE risk_level
                    WHEN 'LOW' THEN 1
                    WHEN 'MEDIUM' THEN 2
                    WHEN 'HIGH' THEN 3
                    WHEN 'CRITICAL' THEN 4
                    ELSE 5
                END;
        """)

        results = cur.fetchall()

    print("\nRésumé des risques :")
    print("NIVEAU | NB_TRAJETS | SCORE_MOYEN | PLUIE_MOY | VENT_MOY")

    for level, count, avg_score, avg_rain, avg_wind in results:
        print(level, count, avg_score, avg_rain, avg_wind)

    conn.close()

    print("\nScore de risque terminé avec succès.")
    print("Table remplie : route_scores")


if __name__ == "__main__":
    main()