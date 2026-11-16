import os
import sqlite3
import logging
from datetime import datetime

logger = logging.getLogger("WarehouseDatabase")

DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data')
DATABASE_PATH = os.path.join(DATABASE_DIR, 'warehouse.db')

# Configurable exchange rate: 1 USD = 83.00 INR
DEFAULT_USD_TO_INR_RATE = 83.00
USD_TO_INR_RATE = float(os.environ.get("USD_TO_INR_RATE", DEFAULT_USD_TO_INR_RATE))
CURRENCY_SYMBOL = "₹"
CURRENCY_CODE = "INR"

ZONE_CITY_MAPPINGS = [
    ('Zone A', 'Bengaluru'),
    ('Zone B', 'Mysuru'),
    ('Zone C', 'Mangaluru'),
    ('Zone D', 'Hubballi'),
    ('Zone E', 'Belagavi'),
    ('Zone F', 'Shivamogga'),
]

def get_db_connection():
    """Returns a connection to the SQLite warehouse database."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database schema with necessary tables and runs idempotent migrations."""
    os.makedirs(DATABASE_DIR, exist_ok=True)
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        full_name TEXT,
        role TEXT DEFAULT 'Administrator',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    )
    ''')

    # Products table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT UNIQUE NOT NULL,
        product_name TEXT NOT NULL,
        category TEXT NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 0,
        unit_price REAL NOT NULL DEFAULT 0.0,
        supplier TEXT NOT NULL,
        warehouse_location TEXT NOT NULL,
        reorder_threshold INTEGER NOT NULL DEFAULT 15,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Stock Transactions table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT NOT NULL,
        transaction_type TEXT NOT NULL,  -- 'INCOMING', 'OUTGOING', 'ADJUSTMENT'
        quantity INTEGER NOT NULL,
        unit_price REAL NOT NULL,
        reference_no TEXT,
        notes TEXT,
        transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products (product_id)
    )
    ''')

    # Alerts table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id TEXT,
        alert_type TEXT NOT NULL,       -- 'OUT_OF_STOCK', 'LOW_STOCK', 'CRITICAL_RISK', 'UNUSUAL_MOVEMENT'
        severity TEXT NOT NULL,         -- 'CRITICAL', 'WARNING', 'INFO'
        message TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE',   -- 'ACTIVE', 'RESOLVED'
        resolved_at TIMESTAMP,
        resolved_by TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Activity logs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS activity_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT,
        action TEXT NOT NULL,
        details TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # System settings table (metadata, currency, active exchange rate)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    conn.commit()

    # Run idempotent migrations for INR currency conversion and Karnataka city names
    migrate_currency_and_zones(conn)

    conn.close()

def migrate_currency_and_zones(conn):
    """
    Idempotent migration:
    - If monetary values are in USD, converts products.unit_price and stock_transactions.unit_price to INR (₹)
      using the documented exchange rate (USD_TO_INR_RATE = 83.00).
    - If already in INR, leaves values untouched to prevent double-conversion.
    - Replaces generic Zone A-F prefixes with Karnataka city names:
      Zone A -> Bengaluru, Zone B -> Mysuru, Zone C -> Mangaluru,
      Zone D -> Hubballi, Zone E -> Belagavi, Zone F -> Shivamogga.
    """
    cursor = conn.cursor()

    # 1. Check existing currency setting
    cursor.execute("SELECT value FROM system_settings WHERE key = 'currency'")
    curr_row = cursor.fetchone()
    already_inr = (curr_row and curr_row[0] == 'INR')

    # Double check by inspecting maximum unit_price
    cursor.execute("SELECT MAX(unit_price) FROM products")
    max_price_row = cursor.fetchone()
    max_price = max_price_row[0] if max_price_row and max_price_row[0] is not None else 0.0

    # If already marked as INR or max price is clearly in INR (> 10000), do not convert monetary values again
    if not already_inr and max_price > 0 and max_price < 5000:
        logger.info(f"Converting database monetary values from USD to INR at rate {USD_TO_INR_RATE}...")
        cursor.execute("UPDATE products SET unit_price = ROUND(unit_price * ?, 2)", (USD_TO_INR_RATE,))
        cursor.execute("UPDATE stock_transactions SET unit_price = ROUND(unit_price * ?, 2)", (USD_TO_INR_RATE,))
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('currency', 'INR')")
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('exchange_rate', ?)", (str(USD_TO_INR_RATE),))
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('currency_symbol', '₹')")
        conn.commit()
        logger.info("Successfully converted inventory and transactions to INR (₹).")
    else:
        # Ensure setting is recorded as INR
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('currency', 'INR')")
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('exchange_rate', ?)", (str(USD_TO_INR_RATE),))
        cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES ('currency_symbol', '₹')")
        conn.commit()

    # 2. Migrate Zone A-F labels to Karnataka City names
    for zone_prefix, city_name in ZONE_CITY_MAPPINGS:
        cursor.execute(
            f"UPDATE products SET warehouse_location = REPLACE(warehouse_location, '{zone_prefix}', '{city_name}') WHERE warehouse_location LIKE '{zone_prefix}%'"
        )
    conn.commit()

def log_activity(username, action, details=""):
    """Records an administrative activity log."""
    try:
        conn = get_db_connection()
        conn.execute(
            "INSERT INTO activity_logs (username, action, details) VALUES (?, ?, ?)",
            (username or "System", action, details)
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error logging activity: {e}")
