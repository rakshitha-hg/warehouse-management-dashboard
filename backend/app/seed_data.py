import os
import csv
import random
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash
from app.database import get_db_connection, init_db

DEMO_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'demo')

SAMPLE_PRODUCTS = [
    # Electronics & IT Hardware -> Bengaluru Warehouse Area
    ("PRD-1001", "Industrial IoT Gateway Router", "Electronics", 35, 20749.17, "Cisco Industrial", "Bengaluru - Aisle 01 - Bin 101", 15),
    ("PRD-1002", "Thermal Barcode Scanner 2D", "Electronics", 8, 9960.00, "Zebra Tech", "Bengaluru - Aisle 01 - Bin 102", 15),
    ("PRD-1003", "Heavy Duty UPS 1500VA", "Electronics", 3, 28261.50, "APC Schneider", "Bengaluru - Aisle 02 - Bin 103", 5),
    ("PRD-1004", "Solid State Drive 2TB NVMe", "Electronics", 75, 12035.00, "Samsung Semiconductor", "Bengaluru - Aisle 02 - Bin 104", 20),
    ("PRD-1005", "Ruggedized Tablet PC 10-inch", "Electronics", 0, 43160.00, "Panasonic Toughbook", "Bengaluru - Aisle 03 - Bin 105", 8),
    ("PRD-1006", "Cat6A Shielded Ethernet Cable (1000ft)", "Electronics", 42, 9545.00, "Belden Cable", "Bengaluru - Aisle 03 - Bin 106", 10),
    ("PRD-1007", "Industrial Smart Sensor Node", "Electronics", 120, 4025.50, "Bosch Connected Devices", "Bengaluru - Aisle 04 - Bin 107", 25),
    ("PRD-1008", "Wireless AP Outdoor Long-Range", "Electronics", 12, 15687.00, "Ubiquiti Networks", "Bengaluru - Aisle 04 - Bin 108", 15),

    # Industrial Machinery & Tools -> Mysuru Warehouse Area
    ("PRD-2001", "Hydraulic Pallet Jack 5500 lbs", "Industrial Tools", 14, 37350.00, "Crown Equipment", "Mysuru - Aisle 01 - Bay 201", 5),
    ("PRD-2002", "Electric Forklift Battery 48V", "Industrial Tools", 2, 232400.00, "EnerSys Power", "Mysuru - Aisle 01 - Bay 202", 3),
    ("PRD-2003", "Pneumatic Impact Wrench Kit", "Industrial Tools", 22, 16185.00, "Ingersoll Rand", "Mysuru - Aisle 02 - Bay 203", 10),
    ("PRD-2004", "Heavy Duty Strapping Tool", "Industrial Tools", 4, 9130.00, "Signode Industrial", "Mysuru - Aisle 02 - Bay 204", 10),
    ("PRD-2005", "Stainless Steel Ball Bearings 6205", "Industrial Tools", 250, 705.50, "SKF Industrial", "Mysuru - Aisle 03 - Bay 205", 50),
    ("PRD-2006", "Industrial Air Compressor 50L", "Industrial Tools", 6, 56440.00, "Atlas Copco", "Mysuru - Aisle 03 - Bay 206", 4),
    ("PRD-2007", "Precision Torque Wrench Digital", "Industrial Tools", 18, 13695.00, "Snap-on Tools", "Mysuru - Aisle 04 - Bay 207", 8),
    ("PRD-2008", "Conveyor Roller Assembly 60mm", "Industrial Tools", 85, 2822.00, "Interroll Systems", "Mysuru - Aisle 04 - Bay 208", 20),

    # Healthcare & Pharma -> Mangaluru Warehouse Area
    ("PRD-3001", "Surgical Nitrile Gloves (Box 100)", "Healthcare", 320, 1203.50, "Ansell Healthcare", "Mangaluru - Aisle 01 - Shelf 301", 80),
    ("PRD-3002", "Digital Infrared Thermometer", "Healthcare", 45, 2656.00, "Omron Medical", "Mangaluru - Aisle 01 - Shelf 302", 20),
    ("PRD-3003", "Hospital Grade Antiseptic 5L", "Healthcare", 12, 3735.00, "Ecolab Health", "Mangaluru - Aisle 02 - Shelf 303", 25),
    ("PRD-3004", "Sterile Syringes 10ml (Pack 100)", "Healthcare", 180, 1867.50, "BD Biosciences", "Mangaluru - Aisle 02 - Shelf 304", 50),
    ("PRD-3005", "N95 Particulate Respirator (Pack 50)", "Healthcare", 5, 2324.00, "3M Health Care", "Mangaluru - Aisle 03 - Shelf 305", 30),
    ("PRD-3006", "Automated External Defibrillator", "Healthcare", 4, 103750.00, "Philips Healthcare", "Mangaluru - Aisle 03 - Shelf 306", 2),
    ("PRD-3007", "Cryogenic Transport Vials 2ml", "Healthcare", 0, 6225.00, "Thermo Fisher Scientific", "Mangaluru - Aisle 04 - Shelf 307", 15),

    # FMCG & Packaged Goods -> Hubballi Warehouse Area
    ("PRD-4001", "Organic Arabica Coffee Beans (10kg)", "FMCG", 65, 7304.00, "Lavazza Wholesale", "Hubballi - Aisle 01 - Pallet 401", 20),
    ("PRD-4002", "Refined Olive Oil Extra Virgin 5L", "FMCG", 90, 3486.00, "Filippo Berio", "Hubballi - Aisle 01 - Pallet 402", 25),
    ("PRD-4003", "Whole Milk Powder Fortified 25kg", "FMCG", 11, 6474.00, "Fonterra Global", "Hubballi - Aisle 02 - Pallet 403", 20),
    ("PRD-4004", "Natural Mineral Water 1L (Case 24)", "FMCG", 140, 1369.50, "Evian Danone", "Hubballi - Aisle 02 - Pallet 404", 40),
    ("PRD-4005", "Basmati Rice Super Kernel 20kg", "FMCG", 8, 3154.00, "Tilda Foods", "Hubballi - Aisle 03 - Pallet 405", 25),
    ("PRD-4006", "Canned San Marzano Tomatoes 2.5kg", "FMCG", 110, 1494.00, "Mutti Parma", "Hubballi - Aisle 03 - Pallet 406", 30),
    ("PRD-4007", "Belgian Dark Chocolate Drops 5kg", "FMCG", 40, 5146.00, "Callebaut Cocoa", "Hubballi - Aisle 04 - Pallet 407", 15),

    # Construction & Safety Gear -> Belagavi Warehouse Area
    ("PRD-5001", "Hard Hat High-Impact Class E", "Safety & Apparel", 150, 1618.50, "MSA Safety", "Belagavi - Aisle 01 - Bin 501", 30),
    ("PRD-5002", "High-Visibility Safety Vest XL", "Safety & Apparel", 210, 705.50, "Pyramex Safety", "Belagavi - Aisle 01 - Bin 502", 40),
    ("PRD-5003", "Steel-Toe Work Boots (Size 10)", "Safety & Apparel", 6, 7387.00, "Timberland PRO", "Belagavi - Aisle 02 - Bin 503", 15),
    ("PRD-5004", "Full Body Fall Protection Harness", "Safety & Apparel", 14, 11205.00, "Miller Honeywell", "Belagavi - Aisle 02 - Bin 504", 10),
    ("PRD-5005", "Cut-Resistant Kevlar Gloves (Pair)", "Safety & Apparel", 95, 996.00, "Superior Glove", "Belagavi - Aisle 03 - Bin 505", 25),
    ("PRD-5006", "Polycarbonate Safety Goggles", "Safety & Apparel", 175, 539.50, "Uvex Safety", "Belagavi - Aisle 03 - Bin 506", 35),
    ("PRD-5007", "Ear Protection Earmuffs 30dB", "Safety & Apparel", 60, 1992.00, "Peltor 3M", "Belagavi - Aisle 04 - Bin 507", 20),

    # Packaging & Logistics Supplies -> Shivamogga Warehouse Area
    ("PRD-6001", "Heavy Duty Cardboard Boxes 24x18x18", "Packaging", 450, 265.60, "Uline Packaging", "Shivamogga - Aisle 01 - Rack 601", 100),
    ("PRD-6002", "Stretch Wrap Film Roll 80 Gauge", "Packaging", 85, 1743.00, "Berry Global", "Shivamogga - Aisle 01 - Rack 602", 25),
    ("PRD-6003", "Reinforced Gummed Paper Tape 3-inch", "Packaging", 120, 954.50, "Intertape Polymer", "Shivamogga - Aisle 02 - Rack 603", 30),
    ("PRD-6004", "Air Pillow Cushioning Roll 500m", "Packaging", 28, 3984.00, "Sealed Air", "Shivamogga - Aisle 02 - Rack 604", 15),
    ("PRD-6005", "Wood Pallets Heat-Treated 48x40", "Packaging", 0, 1535.50, "CHEP Logistics", "Shivamogga - Aisle 03 - Rack 605", 20),
    ("PRD-6006", "Direct Thermal Shipping Labels (4x6)", "Packaging", 220, 1162.00, "Avery Dennison", "Shivamogga - Aisle 03 - Rack 606", 50),
    ("PRD-6007", "Biodegradable Packing Peanuts 14 cu ft", "Packaging", 16, 2199.50, "EcoEnclose", "Shivamogga - Aisle 04 - Rack 607", 10)
]

def seed_database(reset=False):
    """Initializes and seeds realistic database records."""
    init_db()
    conn = get_db_connection()
    cursor = conn.cursor()

    if reset:
        cursor.execute("DELETE FROM activity_logs")
        cursor.execute("DELETE FROM alerts")
        cursor.execute("DELETE FROM stock_transactions")
        cursor.execute("DELETE FROM products")
        cursor.execute("DELETE FROM users")
        conn.commit()

    # 1. Seed Administrator and User Accounts if not present
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash("admin123")
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        """, ("admin", "admin@warehouse.io", hashed_pw, "Chief Warehouse Controller", "Administrator"))
        print("Default administrator seeded: admin@warehouse.io / admin123")

    cursor.execute("SELECT id FROM users WHERE username = 'user'")
    if not cursor.fetchone():
        user_pw = generate_password_hash("user123")
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, ?)
        """, ("user", "user@warehouse.io", user_pw, "Warehouse Operations Staff", "User"))
        conn.commit()
        print("Default user seeded: user@warehouse.io / user123")
    conn.commit()

    # 2. Seed Products
    cursor.execute("SELECT COUNT(*) FROM products")
    prod_count = cursor.fetchone()[0]

    if prod_count == 0 or reset:
        cursor.executemany("""
            INSERT INTO products (
                product_id, product_name, category, quantity, unit_price,
                supplier, warehouse_location, reorder_threshold
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, SAMPLE_PRODUCTS)
        conn.commit()
        print(f"Seeded {len(SAMPLE_PRODUCTS)} products.")

    # 3. Seed Realistic Historical Transactions
    cursor.execute("SELECT COUNT(*) FROM stock_transactions")
    tx_count = cursor.fetchone()[0]

    if tx_count == 0 or reset:
        transactions = []
        now = datetime.now()

        # Seed transactions across the past 120 days
        for prod in SAMPLE_PRODUCTS:
            pid = prod[0]
            category = prod[2]
            price = prod[4]

            # Inbound transaction (initial delivery)
            inbound_qty = random.randint(50, 200)
            inbound_date = now - timedelta(days=random.randint(60, 120))
            transactions.append((
                pid, "INCOMING", inbound_qty, price,
                f"PO-{random.randint(10000, 99999)}", "Initial Stock Inflow",
                inbound_date.strftime("%Y-%m-%d %H:%M:%S")
            ))

            # Mid replenishment for select items
            if random.random() > 0.5:
                mid_qty = random.randint(30, 100)
                mid_date = now - timedelta(days=random.randint(20, 50))
                transactions.append((
                    pid, "INCOMING", mid_qty, price,
                    f"PO-{random.randint(10000, 99999)}", "Scheduled Replenishment",
                    mid_date.strftime("%Y-%m-%d %H:%M:%S")
                ))

            # Outgoing orders
            # Some items have high frequency (fast-moving), some low, some zero (dead stock)
            if pid in ["PRD-1005", "PRD-3007", "PRD-6005"]:
                # Exhausted / zero stock items - huge recent outflow
                for i in range(5):
                    out_date = now - timedelta(days=random.randint(1, 15))
                    transactions.append((
                        pid, "OUTGOING", random.randint(15, 35), price,
                        f"SO-{random.randint(10000, 99999)}", "High Demand Customer Dispatch",
                        out_date.strftime("%Y-%m-%d %H:%M:%S")
                    ))
            elif pid in ["PRD-1002", "PRD-1003", "PRD-2004", "PRD-3005", "PRD-4005", "PRD-5003"]:
                # Low stock items - regular steady drain
                for i in range(4):
                    out_date = now - timedelta(days=random.randint(2, 25))
                    transactions.append((
                        pid, "OUTGOING", random.randint(8, 20), price,
                        f"SO-{random.randint(10000, 99999)}", "Retail Branch Dispatch",
                        out_date.strftime("%Y-%m-%d %H:%M:%S")
                    ))
            elif pid in ["PRD-2005", "PRD-3001", "PRD-4001", "PRD-5001", "PRD-6001"]:
                # High-velocity fast-movers
                for i in range(8):
                    out_date = now - timedelta(days=random.randint(1, 60))
                    transactions.append((
                        pid, "OUTGOING", random.randint(15, 45), price,
                        f"SO-{random.randint(10000, 99999)}", "Bulk Regional Fulfillment",
                        out_date.strftime("%Y-%m-%d %H:%M:%S")
                    ))
                # Add one single-day anomaly spike for PRD-3001
                if pid == "PRD-3001":
                    transactions.append((
                        pid, "OUTGOING", 95, price,
                        f"SO-{random.randint(10000, 99999)}", "ANOMALY: Urgent Emergency Relief Bulk Order",
                        (now - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
                    ))
            elif pid in ["PRD-2002", "PRD-3006"]:
                # High value low frequency
                transactions.append((
                    pid, "OUTGOING", 1, price,
                    f"SO-{random.randint(10000, 99999)}", "Specialist Equipment Delivery",
                    (now - timedelta(days=12)).strftime("%Y-%m-%d %H:%M:%S")
                ))
            elif pid in ["PRD-1008", "PRD-4007"]:
                # Dead stock - no outgoing transactions!
                pass
            else:
                # Normal moderate items
                for i in range(random.randint(2, 4)):
                    out_date = now - timedelta(days=random.randint(3, 45))
                    transactions.append((
                        pid, "OUTGOING", random.randint(5, 15), price,
                        f"SO-{random.randint(10000, 99999)}", "Standard Dispatch",
                        out_date.strftime("%Y-%m-%d %H:%M:%S")
                    ))

        cursor.executemany("""
            INSERT INTO stock_transactions (
                product_id, transaction_type, quantity, unit_price,
                reference_no, notes, transaction_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, transactions)
        conn.commit()
        print(f"Seeded {len(transactions)} stock movement transactions.")

    # 4. Generate sample CSV files for demonstration download
    generate_sample_csv_files()

    conn.close()

def generate_sample_csv_files():
    """Generates sample CSV files for bulk upload testing."""
    os.makedirs(DEMO_DIR, exist_ok=True)

    # 1. Products CSV
    prod_csv_path = os.path.join(DEMO_DIR, "sample_products.csv")
    with open(prod_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "product_id", "product_name", "category", "quantity",
            "unit_price", "supplier", "warehouse_location", "reorder_threshold"
        ])
        for p in SAMPLE_PRODUCTS[:15]:
            writer.writerow(p)

    # 2. Transactions CSV
    tx_csv_path = os.path.join(DEMO_DIR, "sample_transactions.csv")
    with open(tx_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "product_id", "transaction_type", "quantity",
            "unit_price", "reference_no", "notes"
        ])
        for p in SAMPLE_PRODUCTS[:8]:
            writer.writerow([p[0], "INCOMING", 50, p[4], f"PO-{random.randint(10000, 99999)}", "Bulk Replenishment"])
            writer.writerow([p[0], "OUTGOING", 15, p[4], f"SO-{random.randint(10000, 99999)}", "Retail Branch Dispatch"])

    print(f"Demo CSV templates ready at: {DEMO_DIR}")

if __name__ == "__main__":
    seed_database(reset=True)
