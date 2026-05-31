import math
import re
from pathlib import Path
from datetime import datetime, timedelta

import pandas as pd
import psycopg2
from psycopg2.extras import execute_batch

from config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


ROOT_DIR = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT_DIR / "data" / "raw" / "porto_january_2014.csv"

MAX_TRIPS = 5000
POINTS_PER_TRIP = 25
POINT_INTERVAL_SECONDS = 15


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def parse_point(value):
    """
    Accepte plusieurs formats possibles :
    POINT(-8.62 41.15)
    (-8.62, 41.15)
    -8.62,41.15
    [41.15, -8.62]
    
    Retourne toujours :
    latitude, longitude
    """
    text = str(value)

    nums = re.findall(r"-?\d+\.\d+|-?\d+", text)

    if len(nums) < 2:
        return None

    a = float(nums[0])
    b = float(nums[1])

    # Cas 1 : format lon,lat comme POINT(-8.62 41.15)
    if -10 <= a <= -7 and 40 <= b <= 42:
        lon = a
        lat = b
        return lat, lon

    # Cas 2 : format lat,lon comme 41.15,-8.62
    if 40 <= a <= 42 and -10 <= b <= -7:
        lat = a
        lon = b
        return lat, lon

    return None


def parse_time(row):
    """
    Utilise date_depart si disponible, sinon timestamp.
    """
    if "date_depart" in row and pd.notna(row["date_depart"]):
        try:
            return pd.to_datetime(row["date_depart"]).to_pydatetime()
        except Exception:
            pass

    if "timestamp" in row and pd.notna(row["timestamp"]):
        try:
            timestamp = int(row["timestamp"])
            return datetime.fromtimestamp(timestamp)
        except Exception:
            pass

    return datetime.now()


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)

    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def interpolate_points(start_lat, start_lon, end_lat, end_lon, n_points):
    """
    Crée des points intermédiaires entre départ et arrivée.
    """
    points = []

    for i in range(n_points):
        ratio = i / (n_points - 1)

        lat = start_lat + ratio * (end_lat - start_lat)
        lon = start_lon + ratio * (end_lon - start_lon)

        points.append((lat, lon))

    return points


def ensure_tables(conn):
    sql = """
    CREATE EXTENSION IF NOT EXISTS postgis;

    CREATE TABLE IF NOT EXISTS trips (
        id SERIAL PRIMARY KEY,
        trip_id VARCHAR(100),
        taxi_id VARCHAR(50),
        start_time TIMESTAMP,
        end_time TIMESTAMP,
        total_points INTEGER,
        start_lat DOUBLE PRECISION,
        start_lon DOUBLE PRECISION,
        end_lat DOUBLE PRECISION,
        end_lon DOUBLE PRECISION,
        distance_km DOUBLE PRECISION,
        duration_min DOUBLE PRECISION,
        geom GEOMETRY(LineString, 4326)
    );

    CREATE TABLE IF NOT EXISTS gps_positions (
        id SERIAL PRIMARY KEY,
        trip_id VARCHAR(100),
        taxi_id VARCHAR(50),
        point_index INTEGER,
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        event_time TIMESTAMP,
        geom GEOMETRY(Point, 4326)
    );

    CREATE INDEX IF NOT EXISTS idx_trips_taxi_id
    ON trips(taxi_id);

    CREATE INDEX IF NOT EXISTS idx_gps_positions_taxi_id
    ON gps_positions(taxi_id);

    CREATE INDEX IF NOT EXISTS idx_gps_positions_trip_id
    ON gps_positions(trip_id);

    CREATE INDEX IF NOT EXISTS idx_gps_positions_geom
    ON gps_positions USING GIST(geom);

    CREATE INDEX IF NOT EXISTS idx_trips_geom
    ON trips USING GIST(geom);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def clear_old_data(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE gps_positions RESTART IDENTITY;")
        cur.execute("TRUNCATE TABLE trips RESTART IDENTITY;")
        conn.commit()


def insert_data(conn, trips_rows, positions_rows):
    trip_query = """
    INSERT INTO trips (
        trip_id, taxi_id, start_time, end_time, total_points,
        start_lat, start_lon, end_lat, end_lon,
        distance_km, duration_min, geom
    )
    VALUES (
        %(trip_id)s, %(taxi_id)s, %(start_time)s, %(end_time)s, %(total_points)s,
        %(start_lat)s, %(start_lon)s, %(end_lat)s, %(end_lon)s,
        %(distance_km)s, %(duration_min)s,
        ST_SetSRID(
            ST_MakeLine(
                ARRAY[
                    ST_MakePoint(%(start_lon)s, %(start_lat)s),
                    ST_MakePoint(%(end_lon)s, %(end_lat)s)
                ]
            ),
            4326
        )
    );
    """

    position_query = """
    INSERT INTO gps_positions (
        trip_id, taxi_id, point_index, latitude, longitude, event_time, geom
    )
    VALUES (
        %(trip_id)s, %(taxi_id)s, %(point_index)s,
        %(latitude)s, %(longitude)s, %(event_time)s,
        ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)
    );
    """

    with conn.cursor() as cur:
        execute_batch(cur, trip_query, trips_rows, page_size=500)
        execute_batch(cur, position_query, positions_rows, page_size=2000)
        conn.commit()


def main():
    if not CSV_PATH.exists():
        print("Fichier CSV introuvable :", CSV_PATH)
        return

    print("Lecture du fichier CSV...")
    print(CSV_PATH)

    df = pd.read_csv(CSV_PATH)

    print("Colonnes détectées :")
    print(list(df.columns))

    required_columns = ["taxi_id", "trajectory_id", "source_point", "target_point"]
    missing = [col for col in required_columns if col not in df.columns]

    if missing:
        print("Colonnes manquantes :", missing)
        return

    print("Nombre total de lignes CSV :", len(df))

    df = df.head(MAX_TRIPS)

    trips_rows = []
    positions_rows = []

    print(f"Préparation des {len(df)} premiers trajets...")

    for idx, row in df.iterrows():
        taxi_id = str(row["taxi_id"])
        trip_id = str(row["trajectory_id"])

        source = parse_point(row["source_point"])
        target = parse_point(row["target_point"])

        if source is None or target is None:
            continue

        start_lat, start_lon = source
        end_lat, end_lon = target

        distance_km = haversine_km(start_lat, start_lon, end_lat, end_lon)

        if distance_km <= 0 or distance_km > 80:
            continue

        start_time = parse_time(row)
        total_points = POINTS_PER_TRIP
        duration_min = (total_points * POINT_INTERVAL_SECONDS) / 60
        end_time = start_time + timedelta(seconds=total_points * POINT_INTERVAL_SECONDS)

        trips_rows.append({
            "trip_id": trip_id,
            "taxi_id": taxi_id,
            "start_time": start_time,
            "end_time": end_time,
            "total_points": total_points,
            "start_lat": start_lat,
            "start_lon": start_lon,
            "end_lat": end_lat,
            "end_lon": end_lon,
            "distance_km": round(distance_km, 3),
            "duration_min": round(duration_min, 2)
        })

        points = interpolate_points(
            start_lat,
            start_lon,
            end_lat,
            end_lon,
            POINTS_PER_TRIP
        )

        for point_index, (lat, lon) in enumerate(points):
            event_time = start_time + timedelta(seconds=point_index * POINT_INTERVAL_SECONDS)

            positions_rows.append({
                "trip_id": trip_id,
                "taxi_id": taxi_id,
                "point_index": point_index,
                "latitude": lat,
                "longitude": lon,
                "event_time": event_time
            })

        if idx % 500 == 0:
            print(f"Trajets traités : {idx}")

    print("Trajets valides :", len(trips_rows))
    print("Positions GPS préparées :", len(positions_rows))

    conn = connect_db()

    print("Création/vérification des tables...")
    ensure_tables(conn)

    print("Suppression anciennes données trips/gps_positions...")
    clear_old_data(conn)

    print("Insertion dans PostGIS...")
    insert_data(conn, trips_rows, positions_rows)

    conn.close()

    print("Préparation terminée avec succès.")
    print("Tables remplies : trips, gps_positions")


if __name__ == "__main__":
    main()