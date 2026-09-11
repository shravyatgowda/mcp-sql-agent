-- Sample retail schema used to demo and evaluate the MCP text-to-SQL agent.
-- Mirrors the shape of real client pipelines (regions, stores, products, orders)
-- without any real customer or client data.

CREATE TABLE regions (
    region_id   INTEGER PRIMARY KEY,
    region_name TEXT NOT NULL
);

CREATE TABLE stores (
    store_id    INTEGER PRIMARY KEY,
    store_name  TEXT NOT NULL,
    region_id   INTEGER NOT NULL REFERENCES regions(region_id)
);

CREATE TABLE products (
    product_id   INTEGER PRIMARY KEY,
    product_name TEXT NOT NULL,
    category     TEXT NOT NULL,
    unit_price   REAL NOT NULL
);

CREATE TABLE orders (
    order_id     INTEGER PRIMARY KEY,
    store_id     INTEGER NOT NULL REFERENCES stores(store_id),
    product_id   INTEGER NOT NULL REFERENCES products(product_id),
    quantity     INTEGER NOT NULL,
    order_date   TEXT NOT NULL,
    is_returned  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX idx_orders_store   ON orders(store_id);
CREATE INDEX idx_orders_product ON orders(product_id);
CREATE INDEX idx_orders_date    ON orders(order_date);
