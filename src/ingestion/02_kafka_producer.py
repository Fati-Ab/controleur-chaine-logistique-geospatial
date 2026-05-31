import json
import time
import random
import psycopg2
from kafka import KafkaProducer

from src.config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC
)


TOTAL_TAXIS = 304
BATCH_SIZE = 15
SLEEP_SECONDS = 3


def connect_db():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )


def load_positions():
    """
    Charge les positions GPS de 304 taxis réels depuis PostGIS.
    Ensuite, l'envoi Kafka se fera progressivement par batch de 15 taxis.
    """
    query = f"""
    WITH selected_taxis AS (
        SELECT taxi_id
        FROM gps_positions
        GROUP BY taxi_id
        ORDER BY COUNT(*) DESC
        LIMIT {TOTAL_TAXIS}
    )
    SELECT
        gp.taxi_id,
        gp.trip_id,
        gp.point_index,
        gp.latitude,
        gp.longitude,
        gp.event_time
    FROM gps_positions gp
    JOIN selected_taxis st ON gp.taxi_id = st.taxi_id
    ORDER BY gp.point_index, gp.taxi_id, gp.event_time;
    """

    conn = connect_db()
    cur = conn.cursor()
    cur.execute(query)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    positions = []

    for row in rows:
        taxi_id, trip_id, point_index, latitude, longitude, event_time = row

        positions.append({
            "truck_id": f"TAXI-{taxi_id}",
            "trip_id": str(trip_id),
            "point_index": int(point_index),
            "latitude": float(latitude),
            "longitude": float(longitude),
            "event_time": event_time.isoformat()
        })

    return positions


def compute_progress(point_index):
    progress = ((point_index + 1) / 25) * 100
    return min(round(progress, 2), 100)


def compute_status(delay, risk):
    if risk < 5:
        return "OK"
    if risk < 10:
        return "WARNING"
    return "RISK"


def main():
    print("Chargement des positions GPS réelles depuis PostGIS...")
    positions = load_positions()

    if not positions:
        print("Aucune position trouvée dans gps_positions.")
        return

    print(f"Positions chargées : {len(positions)}")
    print(f"Taxis utilisés : {TOTAL_TAXIS}")
    print(f"Envoi progressif : {BATCH_SIZE} taxis par batch")
    print(f"Pause entre batchs : {SLEEP_SECONDS} secondes")

    producer = KafkaProducer(
        bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
        value_serializer=lambda value: json.dumps(value).encode("utf-8")
    )

    print("Kafka Producer réel lancé...")
    print(f"Topic : {KAFKA_TOPIC}")

    index = 0

    while True:
        batch = positions[index:index + BATCH_SIZE]

        if not batch:
            print("Fin du cycle. Redémarrage du flux depuis le début...")
            index = 0
            time.sleep(SLEEP_SECONDS)
            continue

        for pos in batch:
            delay = random.choice([0, 0, 0, 2, 4, 6, 8])
            rain = round(random.uniform(0, 4), 2)
            risk = round(delay + rain * 2 + random.uniform(0, 2), 2)
            status = compute_status(delay, risk)

            message = {
                "truck_id": pos["truck_id"],
                "trip_id": pos["trip_id"],
                "latitude": pos["latitude"],
                "longitude": pos["longitude"],
                "speed": round(random.uniform(20, 70), 2),
                "progress": compute_progress(pos["point_index"]),
                "estimated_delay_minutes": delay,
                "rain": rain,
                "route_risk_score": risk,
                "status": status,
                "event_time": pos["event_time"]
            }

            producer.send(KAFKA_TOPIC, value=message)

            print(
                f"Envoyé : {message['truck_id']} | "
                f"progress={message['progress']}% | "
                f"status={message['status']}"
            )

        producer.flush()

        index += BATCH_SIZE

        print(f"Batch envoyé. Total théorique envoyé jusqu'ici : {index}")
        time.sleep(SLEEP_SECONDS)


if __name__ == "__main__":
    main()