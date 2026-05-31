import json
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_batch

from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


ROOT_DIR = Path(__file__).resolve().parents[2]
EXPORT_DIR = ROOT_DIR / "data" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

COST_PER_KM = 0.8
COST_PER_DELAY_MIN = 0.5


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
    CREATE TABLE IF NOT EXISTS optimized_routes (
        id SERIAL PRIMARY KEY,
        trip_id VARCHAR(100),
        taxi_id VARCHAR(50),
        distance_before_km DOUBLE PRECISION,
        distance_after_km DOUBLE PRECISION,
        delay_before_min DOUBLE PRECISION,
        delay_after_min DOUBLE PRECISION,
        risk_score DOUBLE PRECISION,
        risk_level VARCHAR(30),
        savings_km DOUBLE PRECISION,
        savings_cost DOUBLE PRECISION,
        optimization_status VARCHAR(50),
        created_at TIMESTAMP DEFAULT NOW()
    );

    CREATE INDEX IF NOT EXISTS idx_optimized_routes_trip_id
    ON optimized_routes(trip_id);

    CREATE INDEX IF NOT EXISTS idx_optimized_routes_risk_level
    ON optimized_routes(risk_level);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def clear_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE optimized_routes RESTART IDENTITY;")
        conn.commit()


def load_routes(conn):
    query = """
    SELECT
        rs.trip_id,
        rs.taxi_id,
        rs.distance_km,
        rs.estimated_delay_minutes,
        rs.risk_score,
        rs.risk_level
    FROM route_scores rs
    WHERE rs.distance_km IS NOT NULL
    ORDER BY rs.risk_score DESC
    LIMIT 5000;
    """

    with conn.cursor() as cur:
        cur.execute(query)
        return cur.fetchall()


def optimization_factor(risk_level):
    """
    Plus le risque est élevé, plus l'optimisation peut améliorer la route.
    """
    if risk_level == "LOW":
        return 0.97
    if risk_level == "MEDIUM":
        return 0.90
    if risk_level == "HIGH":
        return 0.82
    if risk_level == "CRITICAL":
        return 0.75
    return 0.95


def delay_factor(risk_level):
    """
    Réduction du retard après optimisation.
    """
    if risk_level == "LOW":
        return 0.95
    if risk_level == "MEDIUM":
        return 0.85
    if risk_level == "HIGH":
        return 0.70
    if risk_level == "CRITICAL":
        return 0.60
    return 0.90


def compute_optimization(rows):
    optimized = []

    for row in rows:
        trip_id, taxi_id, distance_before, delay_before, risk_score, risk_level = row

        distance_before = float(distance_before or 0)
        delay_before = float(delay_before or 0)
        risk_score = float(risk_score or 0)
        risk_level = str(risk_level)

        dist_factor = optimization_factor(risk_level)
        del_factor = delay_factor(risk_level)

        distance_after = round(distance_before * dist_factor, 3)
        delay_after = round(delay_before * del_factor, 2)

        savings_km = round(distance_before - distance_after, 3)

        savings_cost = round(
            savings_km * COST_PER_KM
            + (delay_before - delay_after) * COST_PER_DELAY_MIN,
            2
        )

        optimized.append({
            "trip_id": str(trip_id),
            "taxi_id": str(taxi_id),
            "distance_before_km": round(distance_before, 3),
            "distance_after_km": distance_after,
            "delay_before_min": round(delay_before, 2),
            "delay_after_min": delay_after,
            "risk_score": round(risk_score, 2),
            "risk_level": risk_level,
            "savings_km": savings_km,
            "savings_cost": savings_cost,
            "optimization_status": "OPTIMIZED"
        })

    return optimized


def insert_optimized(conn, rows):
    query = """
    INSERT INTO optimized_routes (
        trip_id,
        taxi_id,
        distance_before_km,
        distance_after_km,
        delay_before_min,
        delay_after_min,
        risk_score,
        risk_level,
        savings_km,
        savings_cost,
        optimization_status
    )
    VALUES (
        %(trip_id)s,
        %(taxi_id)s,
        %(distance_before_km)s,
        %(distance_after_km)s,
        %(delay_before_min)s,
        %(delay_after_min)s,
        %(risk_score)s,
        %(risk_level)s,
        %(savings_km)s,
        %(savings_cost)s,
        %(optimization_status)s
    );
    """

    with conn.cursor() as cur:
        execute_batch(cur, query, rows, page_size=1000)
        conn.commit()


def export_report(conn):
    query = """
    SELECT
        COUNT(*) AS total_routes,
        ROUND(SUM(distance_before_km)::numeric, 2) AS distance_before,
        ROUND(SUM(distance_after_km)::numeric, 2) AS distance_after,
        ROUND(SUM(savings_km)::numeric, 2) AS savings_km,
        ROUND(SUM(delay_before_min)::numeric, 2) AS delay_before,
        ROUND(SUM(delay_after_min)::numeric, 2) AS delay_after,
        ROUND(SUM(savings_cost)::numeric, 2) AS savings_cost
    FROM optimized_routes;
    """

    with conn.cursor() as cur:
        cur.execute(query)
        row = cur.fetchone()

    total_routes, distance_before, distance_after, savings_km, delay_before, delay_after, savings_cost = row

    distance_before = float(distance_before or 0)
    distance_after = float(distance_after or 0)
    savings_km = float(savings_km or 0)
    delay_before = float(delay_before or 0)
    delay_after = float(delay_after or 0)
    savings_cost = float(savings_cost or 0)

    if distance_before > 0:
        savings_percent = round((savings_km / distance_before) * 100, 2)
    else:
        savings_percent = 0

    report = {
        "summary": {
            "total_routes": int(total_routes),
            "distance_before_km": distance_before,
            "distance_after_km": distance_after,
            "savings_km": savings_km,
            "savings_percent": savings_percent,
            "delay_before_min": delay_before,
            "delay_after_min": delay_after,
            "delay_saved_min": round(delay_before - delay_after, 2),
            "savings_cost_eur": savings_cost,
            "estimated_monthly_savings_eur": round(savings_cost * 22, 2)
        }
    }

    output_file = EXPORT_DIR / "optimization_report.json"

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("Rapport exporté :", output_file)

    return report


def main():
    conn = connect_db()

    print("Création table optimized_routes...")
    create_table(conn)

    print("Nettoyage ancienne optimisation...")
    clear_table(conn)

    print("Chargement routes depuis route_scores...")
    rows = load_routes(conn)
    print("Routes chargées :", len(rows))

    if not rows:
        print("Aucune route trouvée. Lance d'abord : python -m src.analysis.06_risk_scoring")
        conn.close()
        return

    print("Calcul optimisation avant/après...")
    optimized_rows = compute_optimization(rows)

    print("Insertion dans PostGIS...")
    insert_optimized(conn, optimized_rows)

    print("Génération rapport JSON...")
    report = export_report(conn)

    conn.close()

    print("\nRésumé optimisation :")
    for key, value in report["summary"].items():
        print(key, ":", value)

    print("\nOptimisation terminée avec succès.")
    print("Table remplie : optimized_routes")


if __name__ == "__main__":
    main()