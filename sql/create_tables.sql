CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS realtime_positions (
    id SERIAL PRIMARY KEY,
    truck_id VARCHAR(20),
    trip_id VARCHAR(100),
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    speed DOUBLE PRECISION,
    progress DOUBLE PRECISION,
    estimated_delay_minutes DOUBLE PRECISION,
    rain DOUBLE PRECISION,
    route_risk_score DOUBLE PRECISION,
    status VARCHAR(30),
    event_time TIMESTAMP DEFAULT NOW(),
    geom GEOMETRY(Point, 4326)
);

CREATE INDEX IF NOT EXISTS idx_realtime_positions_truck
ON realtime_positions(truck_id);

CREATE INDEX IF NOT EXISTS idx_realtime_positions_time
ON realtime_positions(event_time);

CREATE INDEX IF NOT EXISTS idx_realtime_positions_geom
ON realtime_positions
USING GIST(geom);