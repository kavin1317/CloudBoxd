"""
CloudBoxd Synthetic Data Generator
====================================
Generates all 17 source tables with:
- Deterministic output (SEED=42)
- Full referential integrity
- CTT box assignment sequencing (Toyota WMS-inspired)
- Realistic distributions from config.yml

Usage:
    python data_generator/generator.py

Output:
    data/raw/*.csv  (17 files)
"""

import csv
import math
import os
import random
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import yaml
from faker import Faker
from loguru import logger
from rich.console import Console
from rich.progress import track

# ─────────────────────────────────────────────
# Bootstrap
# ─────────────────────────────────────────────
console = Console()
BASE_DIR = Path(__file__).resolve().parent.parent
CONFIG_PATH = Path(__file__).resolve().parent / "config.yml"
OUTPUT_DIR = BASE_DIR / "data" / "raw"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

with open(CONFIG_PATH) as f:
    CFG = yaml.safe_load(f)

SEED = CFG["seed"]
random.seed(SEED)
np.random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

# ─────────────────────────────────────────────
# Date helpers
# ─────────────────────────────────────────────
START_DATE = date.fromisoformat(CFG["date_range"]["start"])
END_DATE   = date.fromisoformat(CFG["date_range"]["end"])
ALL_DATES  = [START_DATE + timedelta(days=i) for i in range((END_DATE - START_DATE).days + 1)]


def rand_time_on(d: date, hour_mean: int = 12, hour_std: int = 2) -> datetime:
    hour   = int(np.clip(np.random.normal(hour_mean, hour_std), 6, 22))
    minute = random.randint(0, 59)
    second = random.randint(0, 59)
    return datetime(d.year, d.month, d.day, hour, minute, second)


def weighted_choice(mapping: dict):
    keys   = list(mapping.keys())
    weights = list(mapping.values())
    return random.choices(keys, weights=weights, k=1)[0]


def write_csv(name: str, rows: list[dict], fieldnames: list[str] | None = None):
    path = OUTPUT_DIR / f"{name}.csv"
    if not rows:
        logger.warning(f"No rows for {name}")
        return
    fields = fieldnames or list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    logger.info(f"  ✓ {name}.csv  →  {len(rows):,} rows")


# ─────────────────────────────────────────────
# 1. subscription_plans  (seed / static)
# ─────────────────────────────────────────────
def gen_subscription_plans() -> list[dict]:
    plans = [
        {"plan_id": "PLAN-BM",  "plan_name": "Basic Monthly",     "plan_price": 49.99,  "meals_per_day": 1, "delivery_frequency": "DAILY",    "is_active": True},
        {"plan_id": "PLAN-PM",  "plan_name": "Premium Monthly",    "plan_price": 89.99,  "meals_per_day": 2, "delivery_frequency": "DAILY",    "is_active": True},
        {"plan_id": "PLAN-CM",  "plan_name": "Corporate Monthly",  "plan_price": 149.99, "meals_per_day": 3, "delivery_frequency": "WEEKDAYS", "is_active": True},
        {"plan_id": "PLAN-PPO", "plan_name": "Pay-Per-Order",      "plan_price": 0.00,   "meals_per_day": 0, "delivery_frequency": "CUSTOM",   "is_active": True},
    ]
    return plans


# ─────────────────────────────────────────────
# 2. addresses
# ─────────────────────────────────────────────
ZONE_ZIPS = {
    "ZONE-A": ["02101", "02102", "02103", "02104", "02105"],
    "ZONE-B": ["02108", "02109", "02110", "02111", "02113"],
    "ZONE-C": ["02115", "02116", "02118", "02119", "02120"],
    "ZONE-D": ["02130", "02131", "02132", "02134", "02135"],
}

def gen_addresses(n: int) -> list[dict]:
    rows = []
    zones = list(ZONE_ZIPS.keys())
    zone_weights = [0.30, 0.30, 0.25, 0.15]
    for i in range(1, n + 1):
        zone = random.choices(zones, weights=zone_weights, k=1)[0]
        zipcode = random.choice(ZONE_ZIPS[zone])
        rows.append({
            "address_id":    f"ADDR-{i:05d}",
            "street":        fake.street_address(),
            "city":          "Boston",
            "state":         "MA",
            "zipcode":       zipcode,
            "delivery_zone": zone,
        })
    return rows


# ─────────────────────────────────────────────
# 3. customers
# ─────────────────────────────────────────────
def gen_customers(n: int, plans: list[dict]) -> list[dict]:
    plan_ids     = [p["plan_id"] for p in plans]
    plan_weights = list(CFG["distributions"]["subscription_plans"].values())
    churn_rate   = CFG["distributions"]["customer_churn"]["monthly_churn_rate"]

    rows = []
    for i in range(1, n + 1):
        signup = fake.date_between(START_DATE, END_DATE - timedelta(days=30))
        # churn probability grows with months since signup
        months_active  = max(1, (END_DATE - signup).days // 30)
        churn_prob     = 1 - (1 - churn_rate) ** months_active
        is_active      = random.random() > churn_prob
        rows.append({
            "customer_id":   f"CUST-{i:05d}",
            "customer_name": fake.name(),
            "email":         fake.unique.email(),
            "phone":         fake.phone_number()[:20],
            "plan_id":       random.choices(plan_ids, weights=plan_weights, k=1)[0],
            "signup_date":   signup.isoformat(),
            "is_active":     is_active,
            "created_at":    datetime.combine(signup, datetime.min.time()).isoformat(),
            "updated_at":    datetime.combine(signup, datetime.min.time()).isoformat(),
        })
    return rows


# ─────────────────────────────────────────────
# 4. customer_addresses
# ─────────────────────────────────────────────
def gen_customer_addresses(customers: list[dict], addresses: list[dict]) -> list[dict]:
    addr_ids = [a["address_id"] for a in addresses]
    rows = []
    for c in customers:
        primary = random.choice(addr_ids)
        rows.append({"customer_id": c["customer_id"], "address_id": primary, "is_primary": True})
        # 10% of customers have a second address
        if random.random() < 0.10:
            secondary = random.choice([a for a in addr_ids if a != primary])
            rows.append({"customer_id": c["customer_id"], "address_id": secondary, "is_primary": False})
    return rows


# ─────────────────────────────────────────────
# 5. menu_items
# ─────────────────────────────────────────────
MENU_DATA = [
    # (name, cuisine, category, price, is_vegetarian)
    ("Masala Dosa",           "South Indian",   "MEAL",     12.99, True),
    ("Idli Sambar",           "South Indian",   "MEAL",     10.99, True),
    ("Chettinad Chicken Curry","South Indian",  "MEAL",     15.99, False),
    ("Rasam Rice",            "South Indian",   "MEAL",     9.99,  True),
    ("Pongal",                "South Indian",   "MEAL",     10.49, True),
    ("Butter Chicken",        "North Indian",   "MEAL",     16.99, False),
    ("Dal Makhani",           "North Indian",   "MEAL",     13.99, True),
    ("Palak Paneer",          "North Indian",   "MEAL",     14.49, True),
    ("Chicken Biryani",       "North Indian",   "MEAL",     17.99, False),
    ("Aloo Paratha",          "North Indian",   "MEAL",     11.49, True),
    ("Rajma Chawal",          "North Indian",   "MEAL",     12.49, True),
    ("Chole Bhature",         "North Indian",   "MEAL",     13.49, True),
    ("Chicken Manchurian",    "Indo-Chinese",   "MEAL",     15.49, False),
    ("Veg Fried Rice",        "Indo-Chinese",   "MEAL",     11.99, True),
    ("Gobi 65",               "Indo-Chinese",   "MEAL",     12.99, True),
    ("Paneer Fried Rice",     "Indo-Chinese",   "MEAL",     13.49, True),
    ("Hyderabadi Biryani",    "Hyderabadi",     "MEAL",     18.99, False),
    ("Mirchi Ka Salan",       "Hyderabadi",     "MEAL",     11.99, True),
    ("Haleem",                "Hyderabadi",     "MEAL",     16.49, False),
    ("Pesarattu",             "South Indian",   "MEAL",     10.99, True),
    ("Uttapam",               "South Indian",   "MEAL",     11.49, True),
    ("Vada Curry",            "South Indian",   "MEAL",     10.99, True),
    ("Egg Curry",             "North Indian",   "MEAL",     13.99, False),
    ("Mutton Rogan Josh",     "North Indian",   "MEAL",     19.99, False),
    ("Kadai Paneer",          "North Indian",   "MEAL",     14.99, True),
    # ADDONS
    ("Raita",                 "Sides",          "ADDON",    2.99,  True),
    ("Pickle",                "Sides",          "ADDON",    1.49,  True),
    ("Papad",                 "Sides",          "ADDON",    1.99,  True),
    ("Extra Rice",            "Sides",          "ADDON",    2.49,  True),
    ("Chapati (2 pcs)",       "Sides",          "ADDON",    2.99,  True),
    # BEVERAGES
    ("Mango Lassi",           "Beverages",      "BEVERAGE", 4.49,  True),
    ("Masala Chai",           "Beverages",      "BEVERAGE", 2.99,  True),
    ("Filter Coffee",         "Beverages",      "BEVERAGE", 2.99,  True),
    ("Nimbu Pani",            "Beverages",      "BEVERAGE", 2.49,  True),
    ("Rose Milk",             "Beverages",      "BEVERAGE", 3.49,  True),
    # DESSERTS
    ("Gulab Jamun (2 pcs)",   "Desserts",       "DESSERT",  3.99,  True),
    ("Kheer",                 "Desserts",       "DESSERT",  3.49,  True),
    ("Halwa",                 "Desserts",       "DESSERT",  3.49,  True),
    ("Rasgulla (2 pcs)",      "Desserts",       "DESSERT",  3.99,  True),
    ("Mysore Pak",            "Desserts",       "DESSERT",  3.49,  True),
    ("Payasam",               "Desserts",       "DESSERT",  3.99,  True),
    ("Jalebi",                "Desserts",       "DESSERT",  2.99,  True),
    ("Ice Cream (Kulfi)",     "Desserts",       "DESSERT",  4.49,  True),
    ("Shrikhand",             "Desserts",       "DESSERT",  3.99,  True),
    ("Basundi",               "Desserts",       "DESSERT",  4.49,  True),
]

def gen_menu_items() -> list[dict]:
    rows = []
    for i, (name, cuisine, category, price, is_veg) in enumerate(MENU_DATA, 1):
        rows.append({
            "menu_item_id":  f"MENU-{i:05d}",
            "item_name":     name,
            "description":   f"Freshly prepared {name} — home-style recipe.",
            "cuisine":       cuisine,
            "category":      category,
            "price":         price,
            "is_vegetarian": is_veg,
            "is_active":     True,
        })
    return rows


# ─────────────────────────────────────────────
# 6. hotboxes
# ─────────────────────────────────────────────
BOX_CAPACITY = {"SMALL": 2, "MEDIUM": 4, "LARGE": 6}

def gen_hotboxes(n: int) -> list[dict]:
    type_weights = CFG["distributions"]["hotbox_types"]
    types        = list(type_weights.keys())
    weights      = list(type_weights.values())
    rows = []
    for i in range(1, n + 1):
        btype = random.choices(types, weights=weights, k=1)[0]
        deployed = fake.date_between(START_DATE - timedelta(days=180), START_DATE)
        rows.append({
            "box_id":             f"BOX-{i:05d}",
            "rfid_tag":           f"RFID-BOS-{i:03d}",
            "box_type":           btype,
            "box_capacity":       BOX_CAPACITY[btype],
            "current_status":     "AVAILABLE",
            "first_deployed":     deployed.isoformat(),
            "total_assignments":  0,
            "created_at":         datetime.combine(deployed, datetime.min.time()).isoformat(),
            "updated_at":         datetime.combine(deployed, datetime.min.time()).isoformat(),
        })
    return rows


# ─────────────────────────────────────────────
# 7. drivers
# ─────────────────────────────────────────────
def gen_drivers(n: int) -> list[dict]:
    rows = []
    for i in range(1, n + 1):
        rows.append({
            "driver_id":      f"DRV-{i:05d}",
            "driver_name":    fake.name(),
            "phone":          fake.phone_number()[:20],
            "vehicle_number": f"MA-{random.randint(1000,9999)}-{fake.lexify('??').upper()}",
            "is_active":      True,
        })
    return rows


# ─────────────────────────────────────────────
# 8–17. Core transactional tables
#   orders, order_items, box_assignments,
#   box_lifecycle_events, deliveries,
#   pickup_schedules, box_maintenance,
#   payments, feedback, loyalty
# ─────────────────────────────────────────────

def get_peak_hour() -> int:
    peak_hours      = CFG["distributions"]["order_hours"]["peak_hours"]
    off_multiplier  = CFG["distributions"]["order_hours"]["off_peak_multiplier"]
    all_hours       = list(range(7, 22))
    hour_weights    = [1.0 if h in peak_hours else off_multiplier for h in all_hours]
    return random.choices(all_hours, weights=hour_weights, k=1)[0]


def select_optimal_box(available: list[dict], items_needed: int) -> dict | None:
    """CTT logic: prefer smallest box that fits; fallback to largest available."""
    fitting   = [b for b in available if b["box_capacity"] >= items_needed]
    if fitting:
        return min(fitting, key=lambda b: b["box_capacity"])
    if available:
        return max(available, key=lambda b: b["box_capacity"])
    return None


def gen_transactions(
    customers:   list[dict],
    addresses:   list[dict],
    menu_items:  list[dict],
    hotboxes:    list[dict],
    drivers:     list[dict],
    cust_addr:   list[dict],
):
    logger.info("Generating transactional tables (this is the heavy lift)...")

    # ── Lookup maps ──────────────────────────────────────────────────────────
    active_customers  = [c for c in customers if c["is_active"]]
    cust_addr_map: dict[str, list[str]] = {}   # customer_id → [address_id]
    for ca in cust_addr:
        cust_addr_map.setdefault(ca["customer_id"], []).append(ca["address_id"])

    addr_zone_map  = {a["address_id"]: a["delivery_zone"] for a in addresses}
    meal_items     = [m for m in menu_items if m["category"] == "MEAL"]
    addon_items    = [m for m in menu_items if m["category"] != "MEAL"]
    driver_ids     = [d["driver_id"] for d in drivers]

    # ── Box pool (mutable state) ──────────────────────────────────────────────
    box_pool         = [dict(b) for b in hotboxes]   # working copy
    box_assign_count: dict[str, int] = {b["box_id"]: 0 for b in box_pool}

    # ── Output accumulators ──────────────────────────────────────────────────
    all_orders:        list[dict] = []
    all_order_items:   list[dict] = []
    all_assignments:   list[dict] = []
    all_events:        list[dict] = []
    all_deliveries:    list[dict] = []
    all_pickups:       list[dict] = []
    all_maintenance:   list[dict] = []
    all_payments:      list[dict] = []
    all_feedback:      list[dict] = []

    event_counter   = 0
    maint_counter   = 0
    pay_counter     = 0
    fb_counter      = 0
    pickup_counter  = 0

    box_return_cfg  = CFG["distributions"]["box_returns"]
    box_cond_cfg    = CFG["distributions"]["box_return_condition"]
    maint_cfg       = CFG["distributions"]["box_maintenance"]
    del_fail_rate   = CFG["distributions"]["delivery_failure_rate"]
    pay_fail_rate   = CFG["distributions"]["payment_failure_rate"]
    fb_rate         = CFG["distributions"]["ratings"]["feedback_rate"]
    fb_mean         = CFG["distributions"]["ratings"]["mean"]
    fb_std          = CFG["distributions"]["ratings"]["std"]
    vol             = CFG["distributions"]["order_volume"]

    def next_event_id() -> str:
        nonlocal event_counter
        event_counter += 1
        return f"EVT-{event_counter:08d}"

    def next_maint_id() -> str:
        nonlocal maint_counter
        maint_counter += 1
        return f"MAINT-{maint_counter:05d}"

    # ── Day-by-day simulation ────────────────────────────────────────────────
    for sim_date in track(ALL_DATES, description="[cyan]Simulating days…"):
        is_weekend   = sim_date.weekday() >= 5
        avg          = vol["weekend_avg"] if is_weekend else vol["weekday_avg"]
        n_orders     = max(1, int(np.random.normal(avg, vol["std_dev"])))
        day_str      = sim_date.strftime("%Y%m%d")

        available_boxes = [b for b in box_pool if b["current_status"] == "AVAILABLE"]

        for order_seq in range(1, n_orders + 1):
            # ── Pick a customer & address ──────────────────────────────────
            if not active_customers:
                break
            cust         = random.choice(active_customers)
            cust_id      = cust["customer_id"]
            addr_options = cust_addr_map.get(cust_id, [])
            if not addr_options:
                continue
            addr_id = random.choice(addr_options)
            zone    = addr_zone_map.get(addr_id, "ZONE-A")

            # ── Build order items ──────────────────────────────────────────
            n_meals    = random.choices([1, 2, 3], weights=[0.50, 0.35, 0.15])[0]
            chosen_meals  = random.choices(meal_items, k=n_meals)
            chosen_addons = random.choices(addon_items, k=random.choices([0, 1, 2], weights=[0.50, 0.35, 0.15])[0])
            chosen_items  = chosen_meals + chosen_addons

            order_id  = f"ORD-{day_str}-{order_seq:03d}"
            order_ts  = rand_time_on(sim_date, hour_mean=get_peak_hour(), hour_std=1)
            order_amount = sum(float(it["price"]) for it in chosen_items)

            all_orders.append({
                "order_id":     order_id,
                "customer_id":  cust_id,
                "order_date":   order_ts.isoformat(),
                "order_amount": round(order_amount, 2),
                "status":       "DELIVERED",
                "address_id":   addr_id,
                "notes":        "",
                "created_at":   order_ts.isoformat(),
            })

            seen_menu: set[str] = set()
            for it in chosen_items:
                mid = it["menu_item_id"]
                if mid in seen_menu:
                    continue
                seen_menu.add(mid)
                all_order_items.append({
                    "order_id":     order_id,
                    "menu_item_id": mid,
                    "quantity":     1,
                    "item_price":   it["price"],
                })

            # ── CTT Box Assignment ─────────────────────────────────────────
            total_items  = len(chosen_meals)   # only meals go in boxes
            remaining    = total_items
            subseq       = 1
            assigned_boxes: list[dict] = []

            while remaining > 0 and available_boxes:
                box = select_optimal_box(available_boxes, remaining)
                if box is None:
                    break
                items_in_box = min(remaining, box["box_capacity"])
                assign_id    = f"BA-{day_str}-{order_seq:03d}-{subseq:04d}"
                assign_ts    = order_ts + timedelta(minutes=random.randint(10, 30))

                all_assignments.append({
                    "assignment_id":   assign_id,
                    "order_id":        order_id,
                    "box_id":          box["box_id"],
                    "sequence_number": order_seq,
                    "subsequence":     f"{subseq:04d}",
                    "assigned_at":     assign_ts.isoformat(),
                    "dispatched_at":   "",
                    "delivered_at":    "",
                    "picked_up_at":    "",
                    "returned_at":     "",
                    "return_condition":"",
                    "turnaround_hours": "",
                    "is_returned":     False,
                })

                # ASSIGNED event
                all_events.append({
                    "event_id":        next_event_id(),
                    "box_id":          box["box_id"],
                    "event_type":      "ASSIGNED",
                    "event_timestamp": assign_ts.isoformat(),
                    "triggered_by":    assign_id,
                    "previous_status": "AVAILABLE",
                    "new_status":      "ASSIGNED",
                    "notes":           f"Assigned to order {order_id}, subseq {subseq:04d}",
                })

                box["current_status"] = "ASSIGNED"
                available_boxes.remove(box)
                assigned_boxes.append((box, assign_id, assign_ts, items_in_box))
                box_assign_count[box["box_id"]] += 1
                remaining   -= items_in_box
                subseq      += 1

            # ── Delivery ───────────────────────────────────────────────────
            zone_cfg      = CFG["distributions"]["delivery_duration"][zone]
            del_duration  = max(15, int(np.random.normal(zone_cfg["mean_min"], zone_cfg["std_min"])))
            departure_ts  = order_ts + timedelta(minutes=random.randint(30, 60))
            delivery_ts   = departure_ts + timedelta(minutes=del_duration)
            is_failed     = random.random() < del_fail_rate
            del_status    = "FAILED" if is_failed else "DELIVERED"

            delivery_id   = f"DEL-{day_str}-{order_seq:03d}"
            all_deliveries.append({
                "delivery_id":          delivery_id,
                "order_id":             order_id,
                "driver_id":            random.choice(driver_ids),
                "address_id":           addr_id,
                "scheduled_time":       departure_ts.isoformat(),
                "actual_departure":     departure_ts.isoformat(),
                "actual_delivery":      delivery_ts.isoformat() if not is_failed else "",
                "delivery_status":      del_status,
                "delivery_duration_min": del_duration if not is_failed else "",
                "failure_reason":       "Customer not available" if is_failed else "",
            })

            # DISPATCHED event for each assigned box
            for box, assign_id, assign_ts, _ in assigned_boxes:
                dispatch_ts = departure_ts + timedelta(seconds=random.randint(0, 120))
                all_events.append({
                    "event_id":        next_event_id(),
                    "box_id":          box["box_id"],
                    "event_type":      "DISPATCHED",
                    "event_timestamp": dispatch_ts.isoformat(),
                    "triggered_by":    assign_id,
                    "previous_status": "ASSIGNED",
                    "new_status":      "IN_TRANSIT",
                    "notes":           f"Dispatched with delivery {delivery_id}",
                })
                box["current_status"] = "IN_TRANSIT"

                # Update assignment dispatched_at
                for a in all_assignments:
                    if a["assignment_id"] == assign_id:
                        a["dispatched_at"] = dispatch_ts.isoformat()
                        break

            if not is_failed:
                for box, assign_id, assign_ts, _ in assigned_boxes:
                    all_events.append({
                        "event_id":        next_event_id(),
                        "box_id":          box["box_id"],
                        "event_type":      "DELIVERED",
                        "event_timestamp": delivery_ts.isoformat(),
                        "triggered_by":    delivery_id,
                        "previous_status": "IN_TRANSIT",
                        "new_status":      "DELIVERED",
                        "notes":           "",
                    })
                    box["current_status"] = "DELIVERED"

                    for a in all_assignments:
                        if a["assignment_id"] == assign_id:
                            a["delivered_at"] = delivery_ts.isoformat()
                            break

                    # ── Pickup scheduling ────────────────────────────────
                    return_bucket = weighted_choice(box_return_cfg)
                    if return_bucket == "same_day":
                        pickup_date = sim_date
                    elif return_bucket == "next_day":
                        pickup_date = sim_date + timedelta(days=1)
                    elif return_bucket == "within_3_days":
                        pickup_date = sim_date + timedelta(days=random.randint(2, 3))
                    elif return_bucket == "overdue":
                        pickup_date = sim_date + timedelta(days=random.randint(4, 7))
                    else:  # lost
                        pickup_date = None

                    pickup_counter += 1
                    pickup_id = f"PKP-{pickup_counter:08d}"
                    pickup_status = "MISSED" if pickup_date is None else "COMPLETED"
                    actual_pickup_ts = None
                    if pickup_date and pickup_date <= END_DATE:
                        actual_pickup_ts = rand_time_on(pickup_date, hour_mean=10, hour_std=2)

                    all_pickups.append({
                        "pickup_id":      pickup_id,
                        "customer_id":    cust_id,
                        "address_id":     addr_id,
                        "box_id":         box["box_id"],
                        "scheduled_date": pickup_date.isoformat() if pickup_date else (sim_date + timedelta(days=1)).isoformat(),
                        "actual_pickup":  actual_pickup_ts.isoformat() if actual_pickup_ts else "",
                        "status":         pickup_status,
                        "driver_id":      random.choice(driver_ids),
                    })

                    # ── Pickup events & return ───────────────────────────
                    pickup_sched_ts = delivery_ts + timedelta(minutes=5)
                    all_events.append({
                        "event_id":        next_event_id(),
                        "box_id":          box["box_id"],
                        "event_type":      "PICKUP_SCHEDULED",
                        "event_timestamp": pickup_sched_ts.isoformat(),
                        "triggered_by":    pickup_id,
                        "previous_status": "DELIVERED",
                        "new_status":      "AWAITING_PICKUP",
                        "notes":           f"Pickup scheduled for {pickup_date}",
                    })
                    box["current_status"] = "AWAITING_PICKUP"

                    if actual_pickup_ts:
                        condition    = weighted_choice(box_cond_cfg)
                        returned_ts  = actual_pickup_ts + timedelta(hours=random.randint(1, 3))
                        turnaround_h = round((returned_ts - assign_ts).total_seconds() / 3600, 2)

                        all_events.append({
                            "event_id":        next_event_id(),
                            "box_id":          box["box_id"],
                            "event_type":      "PICKED_UP",
                            "event_timestamp": actual_pickup_ts.isoformat(),
                            "triggered_by":    pickup_id,
                            "previous_status": "AWAITING_PICKUP",
                            "new_status":      "PICKED_UP",
                            "notes":           "",
                        })
                        all_events.append({
                            "event_id":        next_event_id(),
                            "box_id":          box["box_id"],
                            "event_type":      "INSPECTED",
                            "event_timestamp": returned_ts.isoformat(),
                            "triggered_by":    pickup_id,
                            "previous_status": "PICKED_UP",
                            "new_status":      "RETURNED",
                            "notes":           f"Condition: {condition}",
                        })

                        total_uses = box_assign_count[box["box_id"]]
                        needs_cleaning   = total_uses % maint_cfg["cleaning_every_n_assignments"] == 0
                        needs_inspection = total_uses % maint_cfg["inspection_every_n_assignments"] == 0
                        needs_repair     = condition == "DAMAGED" or random.random() < maint_cfg["repair_probability"]

                        if needs_repair or needs_cleaning or needs_inspection:
                            mtype = "REPAIR" if needs_repair else ("INSPECTION" if needs_inspection else "CLEANING")
                            dur_h = {"REPAIR": maint_cfg["repair_duration_hours"],
                                     "INSPECTION": maint_cfg["inspection_duration_hours"],
                                     "CLEANING": maint_cfg["cleaning_duration_hours"]}[mtype]
                            mstart = returned_ts + timedelta(minutes=30)
                            mend   = mstart + timedelta(hours=dur_h)

                            maint_counter += 1
                            all_maintenance.append({
                                "maintenance_id":   next_maint_id() if False else f"MAINT-{maint_counter:05d}",
                                "box_id":           box["box_id"],
                                "maintenance_type": mtype,
                                "start_date":       mstart.isoformat(),
                                "end_date":         mend.isoformat(),
                                "notes":            f"Post-return {mtype.lower()} after {total_uses} uses",
                                "cost":             round(random.uniform(5, 50) if mtype == "REPAIR" else (2.5 if mtype == "CLEANING" else 10.0), 2),
                            })
                            all_events.append({
                                "event_id":        next_event_id(),
                                "box_id":          box["box_id"],
                                "event_type":      "MAINTENANCE_START",
                                "event_timestamp": mstart.isoformat(),
                                "triggered_by":    f"MAINT-{maint_counter:05d}",
                                "previous_status": "RETURNED",
                                "new_status":      "MAINTENANCE",
                                "notes":           mtype,
                            })
                            all_events.append({
                                "event_id":        next_event_id(),
                                "box_id":          box["box_id"],
                                "event_type":      "MAINTENANCE_END",
                                "event_timestamp": mend.isoformat(),
                                "triggered_by":    f"MAINT-{maint_counter:05d}",
                                "previous_status": "MAINTENANCE",
                                "new_status":      "AVAILABLE",
                                "notes":           f"{mtype} complete",
                            })
                            box["current_status"] = "AVAILABLE"
                            available_boxes.append(box)
                        else:
                            all_events.append({
                                "event_id":        next_event_id(),
                                "box_id":          box["box_id"],
                                "event_type":      "RETURNED_TO_FLEET",
                                "event_timestamp": returned_ts.isoformat(),
                                "triggered_by":    pickup_id,
                                "previous_status": "RETURNED",
                                "new_status":      "AVAILABLE",
                                "notes":           "Cleared for next assignment",
                            })
                            box["current_status"] = "AVAILABLE"
                            available_boxes.append(box)

                        # Update assignment return fields
                        for a in all_assignments:
                            if a["assignment_id"] == assign_id:
                                a["picked_up_at"]    = actual_pickup_ts.isoformat()
                                a["returned_at"]     = returned_ts.isoformat()
                                a["return_condition"]= condition
                                a["turnaround_hours"]= turnaround_h
                                a["is_returned"]     = True
                                break
                    else:
                        # Lost / overdue past end date — mark LOST
                        all_events.append({
                            "event_id":        next_event_id(),
                            "box_id":          box["box_id"],
                            "event_type":      "LOST",
                            "event_timestamp": (sim_date + timedelta(days=8)).isoformat() + "T00:00:00",
                            "triggered_by":    pickup_id,
                            "previous_status": "AWAITING_PICKUP",
                            "new_status":      "LOST",
                            "notes":           "Box not returned within SLA window",
                        })
                        box["current_status"] = "LOST"

            # ── Payment ────────────────────────────────────────────────────
            pay_counter += 1
            is_pay_fail = random.random() < pay_fail_rate
            plan        = cust.get("plan_id", "PLAN-PPO")
            method      = "SUBSCRIPTION" if plan != "PLAN-PPO" else random.choice(["CREDIT_CARD", "DEBIT_CARD", "WALLET"])
            all_payments.append({
                "payment_id":     f"PAY-{pay_counter:05d}",
                "order_id":       order_id,
                "amount":         round(order_amount, 2),
                "payment_method": method,
                "payment_date":   (order_ts + timedelta(minutes=2)).isoformat(),
                "status":         "FAILED" if is_pay_fail else "SUCCESS",
            })

            # ── Feedback ───────────────────────────────────────────────────
            if random.random() < fb_rate and not is_failed:
                fb_counter += 1
                overall = int(np.clip(round(np.random.normal(fb_mean, fb_std)), 1, 5))
                all_feedback.append({
                    "feedback_id":         f"FB-{fb_counter:05d}",
                    "order_id":            order_id,
                    "customer_id":         cust_id,
                    "rating":              overall,
                    "food_rating":         int(np.clip(overall + random.randint(-1, 1), 1, 5)),
                    "delivery_rating":     int(np.clip(overall + random.randint(-1, 1), 1, 5)),
                    "box_condition_rating":int(np.clip(overall + random.randint(-1, 1), 1, 5)),
                    "comments":            random.choice([
                        "Loved the food!", "Great packaging.", "Arrived hot and fresh.",
                        "Delivery was fast.", "Would order again.", "Fantastic meal!",
                        "Slightly late but food was good.", "", "", ""
                    ]),
                    "created_at":          (order_ts + timedelta(hours=random.randint(1, 8))).isoformat(),
                })

    # ── Update hotbox total_assignments ──────────────────────────────────────
    for b in hotboxes:
        b["total_assignments"] = box_assign_count.get(b["box_id"], 0)
        b["updated_at"] = END_DATE.isoformat() + "T00:00:00"

    return (
        all_orders, all_order_items, all_assignments, all_events,
        all_deliveries, all_pickups, all_maintenance,
        all_payments, all_feedback,
    )


# ─────────────────────────────────────────────
# Loyalty tables
# ─────────────────────────────────────────────
def gen_loyalty(customers: list[dict], orders: list[dict]) -> tuple[list[dict], list[dict]]:
    tier_cfg = CFG["distributions"]["loyalty"]["tier_thresholds"]
    ppp      = CFG["distributions"]["loyalty"]["points_per_dollar"]

    # Map customer → orders
    cust_orders: dict[str, list[dict]] = {}
    for o in orders:
        cust_orders.setdefault(o["customer_id"], []).append(o)

    accounts: list[dict] = []
    transactions: list[dict] = []
    txn_counter = 0

    for i, cust in enumerate(customers, 1):
        cid        = cust["customer_id"]
        cust_ords  = sorted(cust_orders.get(cid, []), key=lambda x: x["order_date"])
        points     = 0
        lifetime   = 0
        tier       = "BRONZE"
        tier_ts    = cust["signup_date"] + "T00:00:00" if isinstance(cust["signup_date"], str) else cust["signup_date"].isoformat()

        for o in cust_ords:
            earned = int(float(o["order_amount"]) * ppp)
            points    += earned
            lifetime  += earned

            # Tier upgrade check
            for t, threshold in sorted(tier_cfg.items(), key=lambda x: -x[1]):
                if lifetime >= threshold:
                    if t != tier:
                        tier    = t
                        tier_ts = o["order_date"]
                    break

            txn_counter += 1
            transactions.append({
                "transaction_id":   f"LOYT-{txn_counter:05d}",
                "account_id":       f"LOY-{i:05d}",
                "points_change":    earned,
                "transaction_type": "ORDER_EARNED",
                "transaction_date": o["order_date"],
                "reference_id":     o["order_id"],
            })

            # Occasional redemption (20% of orders for subscribers)
            if cust["plan_id"] != "PLAN-PPO" and random.random() < 0.20 and points >= 200:
                redeemed   = random.randint(100, min(500, points))
                points    -= redeemed
                txn_counter += 1
                transactions.append({
                    "transaction_id":   f"LOYT-{txn_counter:05d}",
                    "account_id":       f"LOY-{i:05d}",
                    "points_change":    -redeemed,
                    "transaction_type": "REDEEMED",
                    "transaction_date": o["order_date"],
                    "reference_id":     o["order_id"],
                })

        accounts.append({
            "account_id":      f"LOY-{i:05d}",
            "customer_id":     cid,
            "tier":            tier,
            "points":          max(0, points),
            "lifetime_points": lifetime,
            "tier_updated_at": tier_ts,
        })

    return accounts, transactions


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────
def main():
    console.rule("[bold cyan]CloudBoxd Data Generator v1.0[/bold cyan]")
    console.print(f"Output → [green]{OUTPUT_DIR}[/green]\n")

    console.print("[bold]Static tables…[/bold]")
    plans     = gen_subscription_plans()
    addresses = gen_addresses(CFG["volumes"]["addresses"])
    menu      = gen_menu_items()
    hotboxes  = gen_hotboxes(CFG["volumes"]["hotboxes"])
    drivers   = gen_drivers(CFG["volumes"]["drivers"])
    customers = gen_customers(CFG["volumes"]["customers"], plans)
    cust_addr = gen_customer_addresses(customers, addresses)

    console.print("\n[bold]Transactional tables…[/bold]")
    (
        orders, order_items, assignments, events,
        deliveries, pickups, maintenance,
        payments, feedback,
    ) = gen_transactions(customers, addresses, menu, hotboxes, drivers, cust_addr)

    console.print("\n[bold]Loyalty tables…[/bold]")
    loyalty_accounts, loyalty_txns = gen_loyalty(customers, orders)

    console.print("\n[bold]Writing CSVs…[/bold]")
    write_csv("subscription_plans",    plans)
    write_csv("addresses",             addresses)
    write_csv("menu_items",            menu)
    write_csv("hotboxes",              hotboxes)
    write_csv("drivers",               drivers)
    write_csv("customers",             customers)
    write_csv("customer_addresses",    cust_addr)
    write_csv("orders",                orders)
    write_csv("order_items",           order_items)
    write_csv("box_assignments",       assignments)
    write_csv("box_lifecycle_events",  events)
    write_csv("deliveries",            deliveries)
    write_csv("pickup_schedules",      pickups)
    write_csv("box_maintenance",       maintenance)
    write_csv("payments",              payments)
    write_csv("feedback",              feedback)
    write_csv("loyalty_accounts",      loyalty_accounts)
    write_csv("loyalty_transactions",  loyalty_txns)

    console.print("\n[bold green]✅ All 17 tables generated.[/bold green]")
    console.print("\n[bold]Row counts:[/bold]")
    for f in sorted(OUTPUT_DIR.glob("*.csv")):
        with open(f) as fh:
            n = sum(1 for _ in fh) - 1
        console.print(f"  {f.name:<35} {n:>8,} rows")


if __name__ == "__main__":
    main()