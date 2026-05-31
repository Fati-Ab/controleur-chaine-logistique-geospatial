import psycopg2
from psycopg2.extras import execute_batch
import pandas as pd
from sklearn.cluster import DBSCAN

from src.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD


SAMPLE_LIMIT = 10000
EPS = 0.0015
MIN_SAMPLES = 20


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def load_positions():
    query = f"""
    SELECT id, taxi_id, trip_id, latitude, longitude
    FROM gps_positions
    WHERE latitude IS NOT NULL
      AND longitude IS NOT NULL
    LIMIT {SAMPLE_LIMIT};
    """

    conn = connect_db()
    df = pd.read_sql(query, conn)
    conn.close()

    return df


def create_cluster_table(conn):
    sql = """
    CREATE TABLE IF NOT EXISTS dbscan_clusters (
        id SERIAL PRIMARY KEY,
        gps_position_id INTEGER,
        taxi_id VARCHAR(50),
        trip_id VARCHAR(100),
        latitude DOUBLE PRECISION,
        longitude DOUBLE PRECISION,
        cluster_id INTEGER,
        cluster_type VARCHAR(30),
        geom GEOMETRY(Point, 4326)
    );

    CREATE INDEX IF NOT EXISTS idx_dbscan_clusters_cluster_id
    ON dbscan_clusters(cluster_id);

    CREATE INDEX IF NOT EXISTS idx_dbscan_clusters_geom
    ON dbscan_clusters USING GIST(geom);
    """

    with conn.cursor() as cur:
        cur.execute(sql)
        conn.commit()


def clear_cluster_table(conn):
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE dbscan_clusters RESTART IDENTITY;")
        conn.commit()


def insert_clusters(conn, df):
    insert_query = """
    INSERT INTO dbscan_clusters (
        gps_position_id, taxi_id, trip_id, latitude, longitude,
        cluster_id, cluster_type, geom
    )
    VALUES (
        %(gps_position_id)s, %(taxi_id)s, %(trip_id)s,
        %(latitude)s, %(longitude)s,
        %(cluster_id)s, %(cluster_type)s,
        ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)
    );
    """

    rows = []

    for _, row in df.iterrows():
        cluster_id = int(row["cluster_id"])

        # On ignore les points bruit/noise pour accélérer l'insertion
        if cluster_id == -1:
            continue

        rows.append({
            "gps_position_id": int(row["id"]),
            "taxi_id": str(row["taxi_id"]),
            "trip_id": str(row["trip_id"]),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "cluster_id": cluster_id,
            "cluster_type": "CONGESTION_ZONE"
        })

    print("Points à insérer :", len(rows))

    if not rows:
        print("Aucun point de cluster à insérer.")
        return

    with conn.cursor() as cur:
        execute_batch(cur, insert_query, rows, page_size=2000)
        conn.commit()


def main():
    print("Chargement des positions GPS depuis PostGIS...")
    df = load_positions()

    if df.empty:
        print("Aucune position trouvée dans gps_positions.")
        return

    print("Positions chargées :", len(df))

    coords = df[["latitude", "longitude"]].values

    print("Application DBSCAN...")
    print(f"eps={EPS}, min_samples={MIN_SAMPLES}")

    model = DBSCAN(
        eps=EPS,
        min_samples=MIN_SAMPLES
    )

    df["cluster_id"] = model.fit_predict(coords)

    nb_clusters = df[df["cluster_id"] != -1]["cluster_id"].nunique()
    nb_noise = int((df["cluster_id"] == -1).sum())

    print("Nombre de clusters détectés :", nb_clusters)
    print("Nombre de points bruit/noise :", nb_noise)

    print("\nTop clusters :")
    print(
        df[df["cluster_id"] != -1]
        .groupby("cluster_id")
        .size()
        .sort_values(ascending=False)
        .head(10)
    )

    conn = connect_db()

    print("Création table dbscan_clusters...")
    create_cluster_table(conn)

    print("Nettoyage ancienne table dbscan_clusters...")
    clear_cluster_table(conn)

    print("Insertion des résultats DBSCAN dans PostGIS...")
    insert_clusters(conn, df)

    conn.close()

    print("DBSCAN terminé avec succès.")
    print("Table remplie : dbscan_clusters")


if __name__ == "__main__":
    main()