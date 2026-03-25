"""
CloudBoxd RFID Event Consumer
================================
Consumes RFID scan events from Kafka and writes them to DuckDB.
This simulates the real-time ingestion layer that feeds the
box lifecycle event stream.

Run: python kafka/consumers/rfid_consumer.py
"""

import json
from datetime import datetime
from pathlib import Path

import duckdb
from confluent_kafka import Consumer, KafkaError
from loguru import logger

# ── Config ────────────────────────────────────────────────────────────────────
KAFKA_BOOTSTRAP = "localhost:9092"
TOPICS = [
    "cloudboxd.hotbox.scanned",
    "cloudboxd.orders.created",
    "cloudboxd.delivery.status",
]

BASE_DIR = Path(__file__).resolve().parent.parent.parent
DB_PATH  = BASE_DIR / "cloudboxd.duckdb"

# ── Consumer setup ────────────────────────────────────────────────────────────
consumer = Consumer({
    "bootstrap.servers":  KAFKA_BOOTSTRAP,
    "group.id":           "cloudboxd-rfid-consumer",
    "auto.offset.reset":  "earliest",
    "enable.auto.commit": True,
})

# ── DuckDB setup ──────────────────────────────────────────────────────────────
def init_streaming_tables(con):
    """Create streaming event tables if they don't exist."""
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.streaming_rfid_events (
            event_id        VARCHAR,
            rfid_tag        VARCHAR,
            box_id          VARCHAR,
            box_type        VARCHAR,
            scan_type       VARCHAR,
            scan_location   VARCHAR,
            scanner_id      VARCHAR,
            signal_strength DOUBLE,
            battery_pct     INTEGER,
            consumed_at     TIMESTAMP,
            raw_payload     VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.streaming_order_events (
            event_id    VARCHAR,
            order_id    VARCHAR,
            customer_id VARCHAR,
            event_type  VARCHAR,
            channel     VARCHAR,
            consumed_at TIMESTAMP,
            raw_payload VARCHAR
        )
    """)
    con.execute("""
        CREATE TABLE IF NOT EXISTS raw.streaming_delivery_events (
            event_id    VARCHAR,
            order_id    VARCHAR,
            driver_id   VARCHAR,
            status      VARCHAR,
            latitude    DOUBLE,
            longitude   DOUBLE,
            consumed_at TIMESTAMP,
            raw_payload VARCHAR
        )
    """)
    logger.info("Streaming tables ready in DuckDB")

def handle_rfid_event(con, payload: dict):
    con.execute("""
        INSERT INTO raw.streaming_rfid_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        payload.get("event_id"),
        payload.get("rfid_tag"),
        payload.get("box_id"),
        payload.get("box_type"),
        payload.get("scan_type"),
        payload.get("scan_location"),
        payload.get("scanner_id"),
        payload.get("signal_strength"),
        payload.get("battery_pct"),
        datetime.utcnow(),
        json.dumps(payload),
    ])

def handle_order_event(con, payload: dict):
    con.execute("""
        INSERT INTO raw.streaming_order_events VALUES (?, ?, ?, ?, ?, ?, ?)
    """, [
        payload.get("event_id"),
        payload.get("order_id"),
        payload.get("customer_id"),
        payload.get("event_type"),
        payload.get("channel"),
        datetime.utcnow(),
        json.dumps(payload),
    ])

def handle_delivery_event(con, payload: dict):
    con.execute("""
        INSERT INTO raw.streaming_delivery_events VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        payload.get("event_id"),
        payload.get("order_id"),
        payload.get("driver_id"),
        payload.get("status"),
        payload.get("latitude"),
        payload.get("longitude"),
        datetime.utcnow(),
        json.dumps(payload),
    ])

# ── Main consumer loop ────────────────────────────────────────────────────────
def main():
    con = duckdb.connect(str(DB_PATH))
    init_streaming_tables(con)

    consumer.subscribe(TOPICS)
    logger.info(f"Subscribed to: {TOPICS}")
    logger.info("Consuming events... Press Ctrl+C to stop\n")

    topic_handlers = {
        "cloudboxd.hotbox.scanned":  handle_rfid_event,
        "cloudboxd.orders.created":  handle_order_event,
        "cloudboxd.delivery.status": handle_delivery_event,
    }

    msg_count = 0
    try:
        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                logger.error(f"Kafka error: {msg.error()}")
                continue

            topic   = msg.topic()
            payload = json.loads(msg.value().decode("utf-8"))
            handler = topic_handlers.get(topic)

            if handler:
                handler(con, payload)
                msg_count += 1
                logger.info(f"[{topic.split('.')[-1].upper()}] consumed event #{msg_count} — {payload.get('event_id')}")

    except KeyboardInterrupt:
        logger.info(f"\nStopped. Total events consumed: {msg_count}")
    finally:
        consumer.close()
        con.close()

if __name__ == "__main__":
    main()
