"""
Builds demo.db: a small SQLite database used to demo and evaluate the
MCP text-to-SQL agent. Run with: python db/seed.py
"""
import sqlite3
import random
import datetime
import os

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "demo.db")
SCHEMA_PATH = os.path.join(HERE, "schema.sql")

REGIONS = ["Karnataka", "Maharashtra", "Delhi NCR", "Tamil Nadu"]
STORES = [
    ("Bengaluru Central", "Karnataka"),
    ("Mysuru Mall", "Karnataka"),
    ("Mumbai Fort", "Maharashtra"),
    ("Pune Camp", "Maharashtra"),
    ("Connaught Place", "Delhi NCR"),
    ("Chennai T Nagar", "Tamil Nadu"),
]
PRODUCTS = [
    ("Classic Sneaker", "Footwear", 1999.0),
    ("Running Shoe", "Footwear", 2999.0),
    ("Cotton Tee", "Apparel", 599.0),
    ("Denim Jacket", "Apparel", 2499.0),
    ("Leather Belt", "Accessories", 899.0),
    ("Canvas Backpack", "Accessories", 1499.0),
    ("Cotton Boxers (Pack of 3)", "Innerwear", 799.0),
]


def build():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    with open(SCHEMA_PATH) as f:
        conn.executescript(f.read())

    cur = conn.cursor()

    region_ids = {}
    for i, name in enumerate(REGIONS, start=1):
        cur.execute("INSERT INTO regions VALUES (?, ?)", (i, name))
        region_ids[name] = i

    store_ids = {}
    for i, (name, region) in enumerate(STORES, start=1):
        cur.execute("INSERT INTO stores VALUES (?, ?, ?)", (i, name, region_ids[region]))
        store_ids[name] = i

    product_ids = {}
    for i, (name, cat, price) in enumerate(PRODUCTS, start=1):
        cur.execute("INSERT INTO products VALUES (?, ?, ?, ?)", (i, name, cat, price))
        product_ids[name] = i

    random.seed(42)
    start_date = datetime.date(2025, 6, 1)
    order_id = 1
    for _ in range(4000):
        store = random.choice(list(store_ids.values()))
        product = random.choice(list(product_ids.values()))
        qty = random.randint(1, 3)
        day_offset = random.randint(0, 120)
        order_date = (start_date + datetime.timedelta(days=day_offset)).isoformat()
        returned = 1 if (random.random() < 0.22) else 0
        cur.execute(
            "INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, store, product, qty, order_date, returned),
        )
        order_id += 1

    conn.commit()
    conn.close()
    print(f"Seeded {DB_PATH} with {order_id - 1} orders.")


if __name__ == "__main__":
    build()
