-- SQLite schema for the synthetic e-commerce case.
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    signup_date TEXT NOT NULL,
    region TEXT NOT NULL,
    city TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS products (
    product_id TEXT PRIMARY KEY,
    product_name TEXT NOT NULL,
    category TEXT NOT NULL,
    list_price REAL NOT NULL CHECK (list_price > 0),
    unit_cost REAL NOT NULL CHECK (unit_cost >= 0),
    popularity_weight REAL,
    is_active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    order_date TEXT NOT NULL,
    sales_channel TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    order_status TEXT NOT NULL,
    discount_rate REAL NOT NULL CHECK (discount_rate >= 0 AND discount_rate <= 1)
);
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    product_id TEXT NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price REAL NOT NULL CHECK (unit_price > 0),
    discount_pct REAL NOT NULL CHECK (discount_pct >= 0 AND discount_pct <= 1)
);
