import json
from pathlib import Path

import psycopg2

from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


# ============================================================
# CHEMINS
# ============================================================

ROOT_DIR = Path(__file__).resolve().parents[2]
EXPORT_DIR = ROOT_DIR / "data" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)


# ============================================================
# CONNEXION POSTGIS
# ============================================================

def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


# ============================================================
# FONCTION GÉNÉRIQUE EXPORT GEOJSON
# ============================================================

def export_geojson(query, output_file):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute(query)
    result = cur.fetchone()

    cur.close()
    conn.close()

    if result is None or result[0] is None:
        print(f"Aucune donnée exportée pour : {output_file}")
        return

    geojson = result[0]

    output_path = EXPORT_DIR / output_file

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False, indent=2)

    print(f"Export créé : {output_path}")


# ============================================================
# EXPORT 1 — POINTS GPS
# ============================================================

def export_gps_points():
    query = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(
            json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(geom)::json,
                'properties', json_build_object(
                    'taxi_id', taxi_id,
                    'trip_id', trip_id,
                    'point_index', point_index,
                    'event_time', event_time
                )
            )
        ), '[]'::json)
    )
    FROM (
        SELECT taxi_id, trip_id, point_index, event_time, geom
        FROM gps_positions
        WHERE geom IS NOT NULL
        LIMIT 20000
    ) AS q;
    """

    export_geojson(query, "kepler_points.geojson")


# ============================================================
# EXPORT 2 — CLUSTERS DBSCAN
# ============================================================

def export_dbscan_clusters():
    query = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(
            json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(geom)::json,
                'properties', json_build_object(
                    'cluster_id', cluster_id,
                    'cluster_type', cluster_type,
                    'taxi_id', taxi_id,
                    'trip_id', trip_id
                )
            )
        ), '[]'::json)
    )
    FROM (
        SELECT cluster_id, cluster_type, taxi_id, trip_id, geom
        FROM dbscan_clusters
        WHERE cluster_id <> -1
          AND geom IS NOT NULL
        LIMIT 10000
    ) AS q;
    """

    export_geojson(query, "dbscan_clusters.geojson")


# ============================================================
# EXPORT 3 — ROUTES AVEC SCORE DE RISQUE
# ============================================================

def export_risk_routes():
    query = """
    SELECT json_build_object(
        'type', 'FeatureCollection',
        'features', COALESCE(json_agg(
            json_build_object(
                'type', 'Feature',
                'geometry', ST_AsGeoJSON(t.geom)::json,
                'properties', json_build_object(
                    'trip_id', t.trip_id,
                    'taxi_id', t.taxi_id,
                    'distance_km', t.distance_km,
                    'duration_min', t.duration_min,
                    'risk_score', rs.risk_score,
                    'risk_level', rs.risk_level,
                    'estimated_delay_minutes', rs.estimated_delay_minutes,
                    'rain_mm', rs.rain_mm,
                    'wind_speed_kmh', rs.wind_speed_kmh,
                    'congestion_flag', rs.congestion_flag
                )
            )
        ), '[]'::json)
    )
    FROM (
        SELECT *
        FROM trips
        WHERE geom IS NOT NULL
        LIMIT 5000
    ) t
    JOIN route_scores rs ON rs.trip_id = t.trip_id;
    """

    export_geojson(query, "risk_routes.geojson")


# ============================================================
# MAIN
# ============================================================

def main():
    print("==============================================")
    print("EXPORT KEPLER.GL")
    print("==============================================")

    print("\n1. Export des points GPS...")
    export_gps_points()

    print("\n2. Export des clusters DBSCAN...")
    export_dbscan_clusters()

    print("\n3. Export des routes avec score de risque...")
    export_risk_routes()

    print("\n==============================================")
    print("Exports terminés avec succès.")
    print("Dossier :", EXPORT_DIR)
    print("==============================================")


if __name__ == "__main__":
    main()