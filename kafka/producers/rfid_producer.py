"""
CloudBoxd RFID Event Producer
================================
Simulates RFID scanner events. Loads reference data from CSVs
to avoid DuckDB lock conflict with the consumer.

Run: python kafka/producers/rfid_producer.py
"""

import csv
import json
import random
import time
from datetime import datetime
from pathlib import Path

from confluent_kafka import Producer
from loguru import logger

KAFKA_BOOTSTRAP = "localhost:9092"
TOPICS = {
    "rfid":     "cloudboxd.hotbox.scanned",
    "orders":   "cloudboxd.orders.created",
    "delivery": "cloudboxd.delivery.status",
}

BASE_DIR = Path(__file__).resolve().parent.parent.parent
RAW_DIR  = BASE_DIR / "data" / "raw"

producer = Producer({
    "bootstrap.servers": KAFKA_BOOTSTRAP,
    "client.id": "cloudboxd-rfid-producer",
})

def delivery_report(err, msg):
    if err:
        logger.error(f"Delivery failed: {err}")

def publish(topic: str, key: str, payload: dict):
    producer.produce(
        topic,
        key=key.encode("utf-8"),
        value=json.dumps(payload).encode("utf-8"),
        callback=delivery_report,
    )
    producer.poll(0)

def load_csv(filename: str, limit: int = 200) -> list[dict]:
    path = RAW_DIR / filename
    with open(path) as f:
        rows = list(csv.DictReader(f))
    return rows[:limit]

def main():
    logger.info("Loading reference data from CSVs...")
    boxes   = load_csv("hotboxes.csv")
    orders  = load_csv("orders.csv", limit=200)
    drivers = load_csv("drivers.csv")
    logger.info(f"Loaded {len(boxes)} boxes, {len(orders)} orders, {len(drivers)} drivers")
    logger.info(f"Streaming to Kafka @ {KAFKA_BOOTSTRAP} — Ctrl+C to stop\n")

    scan_types        = ["DISPATCH_SCAN", "DELIVERY_SCAN", "PICKUP_SCAN"]
    delivery_statuses = ["DISPATCHED", "IN_TRANSIT", "DELIVERED"]
    event_count = 0

    try:
        while True:
            burst = random.randint(3, 8)
            for _ in range(burst):
                etype = random.choices(["rfid","order","delivery"], weights=[0.5,0.25,0.25])[0]

                if etype == "rfid":
                    box = random.choice(boxes)
                    payload = {
                        "event_id":       f"RFID-EVT-{random.randint(100000,999999)}",
                        "rfid_tag":       box["rfid_tag"],
                        "box_id":         box["box_id"],
                        "box_type":       box["box_type"],
                        "scan_type":      random.choice(scan_types),
                        "scan_location":  random.choice(["ZONE-A","ZONE-B","ZONE-C","ZONE-D"]),
                        "scanner_id":     f"SCANNER-{random.randint(1,10):02d}",
                        "timestamp":      datetime.utcnow().isoformat(),
                        "signal_strength": round(random.uniform(-80,-40), 1),
                        "battery_pct":    random.randint(20,100),
                    }
                    publish(TOPICS["rfid"], payload["rfid_tag"], payload)
                    logger.info(f"[RFID]     {payload['rfid_tag']} → {payload['scan_type']} @ {payload['scan_location']}")

                elif etype == "order":
                    order = random.choice(orders)
                    payload = {
                        "event_id":    f"ORD-EVT-{random.randint(100000,999999)}",
                        "order_id":    order["order_id"],
                        "customer_id": order["customer_id"],
                        "event_type":  "ORDER_CREATED",
                        "timestamp":   datetime.utcnow().isoformat(),
                        "channel":     random.choice(["APP","WEB","PHONE"]),
                    }
                    publish(TOPICS["orders"], payload["order_id"], payload)
                    logger.info(f"[ORDER]    {payload['order_id']} → ORDER_CREATED")

                else:
                    order  = random.choice(orders)
                    driver = random.choice(drivers)
                    status = random.choice(delivery_statuses)
                    payload = {
                        "event_id":  f"DEL-EVT-{random.randint(100000,999999)}",
                        "order_id":  order["order_id"],
                        "driver_id": driver["driver_id"],
                        "status":    status,
                        "timestamp": datetime.utcnow().isoformat(),
                        "latitude":  round(random.uniform(42.33,42.40), 6),
                        "longitude": round(random.uniform(-71.12,-71.05), 6),
                    }
                    publish(TOPICS["delivery"], payload["order_id"], payload)
                    logger.info(f"[DELIVERY] {payload['order_id']} → {status}")

                event_count += 1

            producer.flush()
            logger.info(f"--- Burst complete. Total: {event_count} events ---\n")
            time.sleep(random.uniform(1.5, 3.0))

    except KeyboardInterrupt:
        logger.info(f"\nStopped. Total events: {event_count}")
        producer.flush()

if __name__ == "__main__":
    main()
