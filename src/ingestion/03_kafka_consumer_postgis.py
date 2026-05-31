import json
import psycopg2
from kafka import KafkaConsumer
from src.config import (
    DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD,
    KAFKA_BOOTSTRAP_SERVERS, KAFKA_TOPIC
)

conn = psycopg2.connect(
    host=DB_HOST,
    port=DB_PORT,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD
)

consumer = KafkaConsumer(
    KAFKA_TOPIC,
    bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
    auto_offset_reset="latest",
    enable_auto_commit=True,
    group_id="logistics-consumer-group",
    value_deserializer=lambda value: json.loads(value.decode("utf-8"))
)

print("Kafka Consumer lancé...")
print("Insertion dans PostGIS...")

insert_query = """
INSERT INTO realtime_positions (
    truck_id, trip_id, latitude, longitude, speed, progress,
    estimated_delay_minutes, rain, route_risk_score, status, event_time, geom
)
VALUES (
    %(truck_id)s, %(trip_id)s, %(latitude)s, %(longitude)s, %(speed)s, %(progress)s,
    %(estimated_delay_minutes)s, %(rain)s, %(route_risk_score)s, %(status)s,
    %(event_time)s,
    ST_SetSRID(ST_MakePoint(%(longitude)s, %(latitude)s), 4326)
);
"""

for message in consumer:
    data = message.value

    try:
        with conn.cursor() as cur:
            cur.execute(insert_query, data)
            conn.commit()

        print(f"Inséré : {data['truck_id']} | {data['status']} | risque={data['route_risk_score']}")

    except Exception as e:
        conn.rollback()
        print("Erreur insertion :", e)