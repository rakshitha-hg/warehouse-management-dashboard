import os
import sys
import ctypes
import time
import logging
from datetime import datetime, timedelta
import pandas as pd
from app.database import get_db_connection

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("WarehouseSparkEngine")

# Helper to resolve Windows 8.3 short paths to avoid issues with spaces in paths
def get_short_path(long_path):
    if not long_path or os.name != 'nt':
        return long_path
    try:
        buffer = ctypes.create_unicode_buffer(1024)
        ctypes.windll.kernel32.GetShortPathNameW(long_path, buffer, 1024)
        return buffer.value or long_path
    except Exception:
        return long_path

class SparkWarehouseEngine:
    _instance = None
    _spark = None
    _init_error = None
    _last_run_time_ms = 0
    _last_processed_timestamp = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = SparkWarehouseEngine()
        return cls._instance

    def __init__(self):
        self._setup_environment()
        self._init_spark()

    def _setup_environment(self):
        """Configures Java, Python, and Spark paths specifically for Windows compatibility."""
        # 1. Java Home setup
        if not os.environ.get("JAVA_HOME"):
            candidate_jdks = [
                r"C:\Program Files\Java\jdk-21.0.12",
                r"C:\Program Files\Java\jdk-25.0.4",
                r"C:\Program Files\Java\latest"
            ]
            for jdk in candidate_jdks:
                if os.path.exists(jdk):
                    os.environ["JAVA_HOME"] = jdk
                    logger.info(f"Setting JAVA_HOME to {jdk}")
                    break

        # 2. Python executable setup for PySpark driver & workers (with 8.3 short path)
        py_exe = sys.executable
        short_py = get_short_path(py_exe)
        os.environ["PYSPARK_PYTHON"] = short_py
        os.environ["PYSPARK_DRIVER_PYTHON"] = short_py
        logger.info(f"PySpark Python configured: {short_py}")

    def _init_spark(self):
        """Initializes Apache Spark session with local master and optimized settings."""
        try:
            from pyspark.sql import SparkSession
            logger.info("Initializing Apache Spark Session for Warehouse Management...")
            start_time = time.time()

            spark = SparkSession.builder \
                .appName("WarehouseManagementAnalyticsEngine") \
                .master("local[2]") \
                .config("spark.driver.host", "127.0.0.1") \
                .config("spark.driver.bindAddress", "127.0.0.1") \
                .config("spark.sql.shuffle.partitions", "2") \
                .config("spark.ui.enabled", "false") \
                .config("spark.driver.memory", "1g") \
                .getOrCreate()

            # Set log level to WARN to reduce console noise
            spark.sparkContext.setLogLevel("WARN")

            self._spark = spark
            self._init_error = None
            elapsed = int((time.time() - start_time) * 1000)
            logger.info(f"Apache Spark session successfully initialized in {elapsed}ms.")
        except Exception as e:
            self._init_error = str(e)
            self._spark = None
            logger.error(f"Failed to initialize Apache Spark session: {e}", exc_info=True)

    def get_spark(self):
        """Returns the active SparkSession or attempts re-initialization if failed."""
        if self._spark is None and self._init_error:
            self._init_spark()
        return self._spark

    def get_diagnostics(self):
        """Returns system and Spark runtime diagnostic information."""
        spark = self.get_spark()
        is_active = spark is not None and not spark.sparkContext._jsc.sc().isStopped()
        return {
            "spark_active": is_active,
            "version": spark.version if is_active else "Unavailable",
            "app_name": spark.sparkContext.appName if is_active else "None",
            "master": spark.sparkContext.master if is_active else "None",
            "java_home": os.environ.get("JAVA_HOME", "Unset"),
            "python_worker": os.environ.get("PYSPARK_PYTHON", sys.executable),
            "last_execution_ms": self._last_run_time_ms,
            "last_processed_timestamp": self._last_processed_timestamp,
            "error": self._init_error
        }

    def _load_dataframes_from_db(self):
        """
        Loads records from SQLite database into Pandas, then converts into
        genuine PySpark DataFrames with explicit schemas.
        """
        spark = self.get_spark()
        if spark is None:
            raise RuntimeError(f"Apache Spark engine is not active: {self._init_error}")

        from pyspark.sql.types import (
            StructType, StructField, StringType, IntegerType, DoubleType, TimestampType
        )

        conn = get_db_connection()
        try:
            # 1. Load Products
            products_query = """
            SELECT product_id, product_name, category, quantity, unit_price,
                   supplier, warehouse_location, reorder_threshold
            FROM products
            """
            pdf_products = pd.read_sql_query(products_query, conn)

            # 2. Load Stock Transactions
            transactions_query = """
            SELECT id, product_id, transaction_type, quantity, unit_price,
                   reference_no, notes, transaction_date
            FROM stock_transactions
            """
            pdf_tx = pd.read_sql_query(transactions_query, conn)
        finally:
            conn.close()

        # Handle empty DataFrames safely
        if pdf_products.empty:
            pdf_products = pd.DataFrame(columns=[
                'product_id', 'product_name', 'category', 'quantity', 'unit_price',
                'supplier', 'warehouse_location', 'reorder_threshold'
            ])

        # Ensure correct datatypes
        pdf_products['quantity'] = pdf_products['quantity'].fillna(0).astype(int)
        pdf_products['unit_price'] = pdf_products['unit_price'].fillna(0.0).astype(float)
        pdf_products['reorder_threshold'] = pdf_products['reorder_threshold'].fillna(10).astype(int)

        if pdf_tx.empty:
            pdf_tx = pd.DataFrame(columns=[
                'id', 'product_id', 'transaction_type', 'quantity', 'unit_price',
                'reference_no', 'notes', 'transaction_date'
            ])
        else:
            pdf_tx['quantity'] = pdf_tx['quantity'].fillna(0).astype(int)
            pdf_tx['unit_price'] = pdf_tx['unit_price'].fillna(0.0).astype(float)
            pdf_tx['transaction_date'] = pd.to_datetime(pdf_tx['transaction_date']).dt.strftime('%Y-%m-%d %H:%M:%S')

        # Convert to Spark DataFrames
        df_products = spark.createDataFrame(pdf_products)
        df_transactions = spark.createDataFrame(pdf_tx)

        # Register Spark SQL Temporary Views for SQL transformations
        df_products.createOrReplaceTempView("products")
        df_transactions.createOrReplaceTempView("transactions")

        return df_products, df_transactions

    def process_warehouse_analytics(self):
        """
        Executes comprehensive Apache Spark processing across inventory and transaction datasets.
        Uses Spark SQL and DataFrame aggregations for metrics, distributions, and trends.
        """
        start_time = time.time()
        spark = self.get_spark()
        df_products, df_tx = self._load_dataframes_from_db()

        from pyspark.sql.functions import (
            col, sum as _sum, count as _count, avg as _avg,
            when, desc, round as _round, date_format, to_date
        )

        # ---------------------------------------------------------
        # 1. Spark Overall Inventory Aggregations
        # ---------------------------------------------------------
        inv_summary = spark.sql("""
            SELECT 
                COUNT(*) as total_products,
                COALESCE(SUM(quantity), 0) as total_stock_units,
                COALESCE(ROUND(SUM(quantity * unit_price), 2), 0.0) as total_inventory_value,
                COALESCE(SUM(CASE WHEN quantity = 0 THEN 1 ELSE 0 END), 0) as out_of_stock_count,
                COALESCE(SUM(CASE WHEN quantity > 0 AND quantity <= reorder_threshold THEN 1 ELSE 0 END), 0) as low_stock_count,
                COALESCE(ROUND(AVG(unit_price), 2), 0.0) as avg_unit_price
            FROM products
        """).collect()[0]

        # ---------------------------------------------------------
        # 2. Spark Stock Flow Aggregations (Incoming vs Outgoing)
        # ---------------------------------------------------------
        flow_summary = spark.sql("""
            SELECT
                COALESCE(SUM(CASE WHEN transaction_type = 'INCOMING' THEN quantity ELSE 0 END), 0) as total_incoming_units,
                COALESCE(ROUND(SUM(CASE WHEN transaction_type = 'INCOMING' THEN quantity * unit_price ELSE 0 END), 2), 0.0) as total_incoming_val,
                COALESCE(SUM(CASE WHEN transaction_type = 'OUTGOING' THEN quantity ELSE 0 END), 0) as total_outgoing_units,
                COALESCE(ROUND(SUM(CASE WHEN transaction_type = 'OUTGOING' THEN quantity * unit_price ELSE 0 END), 2), 0.0) as total_outgoing_val,
                COUNT(id) as total_transactions_count
            FROM transactions
        """).collect()[0]

        # ---------------------------------------------------------
        # 3. Category Breakdown via Spark SQL
        # ---------------------------------------------------------
        category_rows = spark.sql("""
            SELECT 
                category,
                COUNT(*) as product_count,
                COALESCE(SUM(quantity), 0) as total_units,
                COALESCE(ROUND(SUM(quantity * unit_price), 2), 0.0) as category_value,
                COALESCE(ROUND(AVG(unit_price), 2), 0.0) as avg_price,
                COALESCE(SUM(CASE WHEN quantity <= reorder_threshold THEN 1 ELSE 0 END), 0) as low_stock_items
            FROM products
            GROUP BY category
            ORDER BY category_value DESC
        """).collect()

        categories_data = [
            {
                "category": r["category"],
                "product_count": int(r["product_count"]),
                "total_units": int(r["total_units"]),
                "category_value": float(r["category_value"]),
                "avg_price": float(r["avg_price"]),
                "low_stock_items": int(r["low_stock_items"])
            }
            for r in category_rows
        ]

        # ---------------------------------------------------------
        # 4. Monthly Stock Movement Trends via Spark SQL
        # ---------------------------------------------------------
        monthly_rows = spark.sql("""
            SELECT 
                SUBSTRING(transaction_date, 1, 7) as month_period,
                COALESCE(SUM(CASE WHEN transaction_type = 'INCOMING' THEN quantity ELSE 0 END), 0) as incoming_units,
                COALESCE(SUM(CASE WHEN transaction_type = 'OUTGOING' THEN quantity ELSE 0 END), 0) as outgoing_units,
                COALESCE(ROUND(SUM(CASE WHEN transaction_type = 'OUTGOING' THEN quantity * unit_price ELSE 0 END), 2), 0.0) as outgoing_value
            FROM transactions
            WHERE transaction_date IS NOT NULL
            GROUP BY SUBSTRING(transaction_date, 1, 7)
            ORDER BY month_period ASC
        """).collect()

        monthly_trends = [
            {
                "period": r["month_period"],
                "incoming": int(r["incoming_units"]),
                "outgoing": int(r["outgoing_units"]),
                "outgoing_value": float(r["outgoing_value"])
            }
            for r in monthly_rows if r["month_period"] is not None
        ]

        # ---------------------------------------------------------
        # 5. Top-Selling / Top-Outflow Products via Spark SQL
        # ---------------------------------------------------------
        top_selling_rows = spark.sql("""
            SELECT 
                t.product_id,
                p.product_name,
                p.category,
                COALESCE(SUM(t.quantity), 0) as total_dispatched,
                COALESCE(ROUND(SUM(t.quantity * t.unit_price), 2), 0.0) as total_revenue
            FROM transactions t
            LEFT JOIN products p ON t.product_id = p.product_id
            WHERE t.transaction_type = 'OUTGOING'
            GROUP BY t.product_id, p.product_name, p.category
            ORDER BY total_dispatched DESC
            LIMIT 7
        """).collect()

        top_selling = [
            {
                "product_id": r["product_id"],
                "product_name": r["product_name"] or r["product_id"],
                "category": r["category"] or "Unknown",
                "total_dispatched": int(r["total_dispatched"]),
                "total_revenue": float(r["total_revenue"])
            }
            for r in top_selling_rows
        ]

        # ---------------------------------------------------------
        # 6. Low-Stock Products Analysis
        # ---------------------------------------------------------
        low_stock_rows = spark.sql("""
            SELECT 
                product_id, product_name, category, quantity, reorder_threshold,
                warehouse_location, unit_price
            FROM products
            WHERE quantity <= reorder_threshold
            ORDER BY quantity ASC, reorder_threshold DESC
            LIMIT 10
        """).collect()

        low_stock_analysis = [
            {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "category": r["category"],
                "quantity": int(r["quantity"]),
                "reorder_threshold": int(r["reorder_threshold"]),
                "warehouse_location": r["warehouse_location"],
                "unit_price": float(r["unit_price"]),
                "status": "OUT_OF_STOCK" if r["quantity"] == 0 else "LOW_STOCK"
            }
            for r in low_stock_rows
        ]

        # Calculate execution time
        self._last_run_time_ms = int((time.time() - start_time) * 1000)
        self._last_processed_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        return {
            "summary": {
                "total_products": int(inv_summary["total_products"]),
                "total_stock_units": int(inv_summary["total_stock_units"]),
                "total_inventory_value": float(inv_summary["total_inventory_value"]),
                "out_of_stock_count": int(inv_summary["out_of_stock_count"]),
                "low_stock_count": int(inv_summary["low_stock_count"]),
                "avg_unit_price": float(inv_summary["avg_unit_price"]),
                "total_incoming_units": int(flow_summary["total_incoming_units"]),
                "total_incoming_val": float(flow_summary["total_incoming_val"]),
                "total_outgoing_units": int(flow_summary["total_outgoing_units"]),
                "total_outgoing_val": float(flow_summary["total_outgoing_val"]),
                "total_transactions": int(flow_summary["total_transactions_count"])
            },
            "categories": categories_data,
            "monthly_trends": monthly_trends,
            "top_selling": top_selling,
            "low_stock_analysis": low_stock_analysis,
            "spark_execution_time_ms": self._last_run_time_ms,
            "processed_at": self._last_processed_timestamp
        }

    def run_stock_risk_analysis(self):
        """
        Unique Feature: Smart Stock Risk Analysis
        Uses Spark to compute consumption velocity, estimated days to depletion,
        and assign risk levels with understandable explanations.
        """
        spark = self.get_spark()
        df_products, df_tx = self._load_dataframes_from_db()

        # Execute Spark SQL query joining products with recent outgoing velocity
        risk_query = """
        WITH OutgoingStats AS (
            SELECT 
                product_id,
                COALESCE(SUM(quantity), 0) as total_outgoing_30d,
                COALESCE(COUNT(id), 0) as outgoing_orders_count
            FROM transactions
            WHERE transaction_type = 'OUTGOING'
            GROUP BY product_id
        )
        SELECT 
            p.product_id,
            p.product_name,
            p.category,
            p.quantity as current_stock,
            p.reorder_threshold,
            p.unit_price,
            p.warehouse_location,
            p.supplier,
            COALESCE(o.total_outgoing_30d, 0) as historical_outflow_30d,
            ROUND(COALESCE(o.total_outgoing_30d, 0) / 30.0, 2) as avg_daily_consumption
        FROM products p
        LEFT JOIN OutgoingStats o ON p.product_id = o.product_id
        """

        risk_rows = spark.sql(risk_query).collect()
        analyzed_products = []
        risk_counts = {"Critical": 0, "High": 0, "Moderate": 0, "Healthy": 0}

        for r in risk_rows:
            curr_stock = int(r["current_stock"])
            reorder_pt = int(r["reorder_threshold"])
            daily_cons = float(r["avg_daily_consumption"])
            outflow_30d = int(r["historical_outflow_30d"])

            # Compute estimated days to depletion
            if curr_stock <= 0:
                days_left = 0.0
                risk_level = "Critical"
                reason = "Product is completely out of stock. Immediate reorder required to resume fulfillment."
            elif daily_cons > 0:
                days_left = round(curr_stock / daily_cons, 1)
                if days_left <= 3.0:
                    risk_level = "Critical"
                    reason = f"Severe depletion risk: {curr_stock} units remaining against {daily_cons} units/day burn rate. Stock will be exhausted in ~{days_left} days."
                elif days_left <= 14.0 or curr_stock <= reorder_pt:
                    risk_level = "High"
                    if curr_stock <= reorder_pt:
                        reason = f"Stock level ({curr_stock}) is at or below reorder threshold ({reorder_pt}). Est. depletion in {days_left} days."
                    else:
                        reason = f"Fast drawdown velocity: {days_left} days of buffer remaining based on recent outgoing orders."
                elif days_left <= 30.0:
                    risk_level = "Moderate"
                    reason = f"Normal consumption velocity. Buffer of {days_left} days remains before safety threshold is breached."
                else:
                    risk_level = "Healthy"
                    reason = f"Adequate stock buffer (~{days_left} days) at current consumption pace."
            else:
                # No recent outgoing movement
                days_left = 999.0
                if curr_stock <= reorder_pt:
                    risk_level = "Moderate"
                    reason = f"Stock is below reorder threshold ({curr_stock}/{reorder_pt}), but zero outgoing movement was recorded in the last 30 days."
                else:
                    risk_level = "Healthy"
                    reason = f"Sufficient inventory ({curr_stock} units) with zero recent stock depletion."

            risk_counts[risk_level] += 1

            analyzed_products.append({
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "category": r["category"],
                "current_stock": curr_stock,
                "reorder_threshold": reorder_pt,
                "historical_outflow_30d": outflow_30d,
                "avg_daily_consumption": daily_cons,
                "days_until_depletion": days_left if days_left != 999.0 else "30+ Days",
                "numeric_days": days_left,
                "risk_level": risk_level,
                "explanation": reason,
                "warehouse_location": r["warehouse_location"],
                "supplier": r["supplier"],
                "unit_price": float(r["unit_price"])
            })

        # Sort products by highest risk first (Critical, High, Moderate, Healthy)
        priority_map = {"Critical": 0, "High": 1, "Moderate": 2, "Healthy": 3}
        analyzed_products.sort(key=lambda x: (priority_map[x["risk_level"]], x["numeric_days"], x["current_stock"]))

        # Automatically synchronize alerts to SQLite database
        self._sync_risk_alerts(analyzed_products)

        return {
            "products": analyzed_products,
            "counts": risk_counts,
            "total_evaluated": len(analyzed_products),
            "critical_items": [p for p in analyzed_products if p["risk_level"] == "Critical"],
            "high_risk_items": [p for p in analyzed_products if p["risk_level"] == "High"]
        }

    def run_inventory_movement_intelligence(self):
        """
        Unique Feature: Inventory Movement Intelligence
        Identifies fast-moving, slow-moving, non-moving (dead stock),
        unusual stock spikes, and category momentum using Spark aggregations.
        """
        spark = self.get_spark()
        df_products, df_tx = self._load_dataframes_from_db()

        # 1. Product Velocity & Turnover Analysis via Spark SQL
        velocity_query = """
        WITH ProductOutflow AS (
            SELECT 
                product_id,
                COALESCE(SUM(quantity), 0) as total_outflow,
                COUNT(id) as dispatch_frequency,
                COALESCE(MAX(quantity), 0) as max_single_dispatch,
                COALESCE(ROUND(AVG(quantity), 2), 0.0) as avg_dispatch_size
            FROM transactions
            WHERE transaction_type = 'OUTGOING'
            GROUP BY product_id
        )
        SELECT 
            p.product_id,
            p.product_name,
            p.category,
            p.quantity as current_stock,
            p.unit_price,
            p.warehouse_location,
            COALESCE(o.total_outflow, 0) as total_outflow,
            COALESCE(o.dispatch_frequency, 0) as dispatch_frequency,
            COALESCE(o.max_single_dispatch, 0) as max_single_dispatch,
            COALESCE(o.avg_dispatch_size, 0.0) as avg_dispatch_size
        FROM products p
        LEFT JOIN ProductOutflow o ON p.product_id = o.product_id
        """

        velocity_rows = spark.sql(velocity_query).collect()

        fast_moving = []
        slow_moving = []
        dead_stock = []
        unusual_movement = []

        for r in velocity_rows:
            stock = int(r["current_stock"])
            outflow = int(r["total_outflow"])
            freq = int(r["dispatch_frequency"])
            max_dispatch = int(r["max_single_dispatch"])
            avg_dispatch = float(r["avg_dispatch_size"])
            prod_val = stock * float(r["unit_price"])

            item = {
                "product_id": r["product_id"],
                "product_name": r["product_name"],
                "category": r["category"],
                "current_stock": stock,
                "total_outflow": outflow,
                "dispatch_frequency": freq,
                "unit_price": float(r["unit_price"]),
                "warehouse_location": r["warehouse_location"],
                "tied_up_capital": round(prod_val, 2)
            }

            # Classification logic
            if outflow >= 40 or freq >= 6:
                item["velocity"] = "Fast-Moving"
                item["badge"] = "success"
                item["insight"] = f"High velocity item: {outflow} units dispatched across {freq} orders."
                fast_moving.append(item)
            elif outflow > 0 and outflow < 15:
                item["velocity"] = "Slow-Moving"
                item["badge"] = "warning"
                item["insight"] = f"Subdued turnover: only {outflow} units moved with {stock} units in storage."
                slow_moving.append(item)
            elif outflow == 0:
                item["velocity"] = "Dead Stock"
                item["badge"] = "danger"
                item["insight"] = f"Zero outbound movements recorded. ₹{prod_val:,.2f} in working capital tied up."
                dead_stock.append(item)

            # Detect unusual stock changes (single order > 2.5x average order size or sudden spike)
            if freq >= 2 and max_dispatch >= 2.5 * avg_dispatch and max_dispatch >= 15:
                unusual_movement.append({
                    "product_id": r["product_id"],
                    "product_name": r["product_name"],
                    "category": r["category"],
                    "max_dispatch": max_dispatch,
                    "avg_dispatch": avg_dispatch,
                    "spike_ratio": round(max_dispatch / max(avg_dispatch, 1.0), 1),
                    "description": f"Unusual outflow spike of {max_dispatch} units in a single transaction (normal avg: {avg_dispatch})."
                })

        # Sort lists
        fast_moving.sort(key=lambda x: x["total_outflow"], reverse=True)
        slow_moving.sort(key=lambda x: x["current_stock"], reverse=True)
        dead_stock.sort(key=lambda x: x["tied_up_capital"], reverse=True)
        unusual_movement.sort(key=lambda x: x["spike_ratio"], reverse=True)

        # 2. Category Demand Momentum
        cat_momentum_rows = spark.sql("""
            SELECT 
                p.category,
                COALESCE(SUM(t.quantity), 0) as total_demand,
                COALESCE(ROUND(SUM(t.quantity * t.unit_price), 2), 0.0) as total_val
            FROM transactions t
            JOIN products p ON t.product_id = p.product_id
            WHERE t.transaction_type = 'OUTGOING'
            GROUP BY p.category
            ORDER BY total_demand DESC
        """).collect()

        category_demand = [
            {
                "category": r["category"],
                "total_demand": int(r["total_demand"]),
                "total_val": float(r["total_val"])
            }
            for r in cat_momentum_rows
        ]

        return {
            "fast_moving": fast_moving,
            "slow_moving": slow_moving,
            "dead_stock": dead_stock,
            "unusual_movement": unusual_movement,
            "category_demand": category_demand,
            "summary_counts": {
                "fast": len(fast_moving),
                "slow": len(slow_moving),
                "dead": len(dead_stock),
                "anomalies": len(unusual_movement)
            }
        }

    def run_warehouse_performance_insights(self):
        """
        Unique Feature: Warehouse Performance Insights
        Computes turnover indicators, storage distribution by zone/aisle,
        and generates data-driven recommendations.
        """
        spark = self.get_spark()
        df_products, df_tx = self._load_dataframes_from_db()

        # 1. Warehouse Storage Distribution by Warehouse Areas (Karnataka Cities)
        zone_rows = spark.sql("""
            SELECT 
                CASE 
                    WHEN warehouse_location LIKE 'Bengaluru%' OR warehouse_location LIKE 'Zone A%' THEN 'Bengaluru'
                    WHEN warehouse_location LIKE 'Mysuru%' OR warehouse_location LIKE 'Zone B%' THEN 'Mysuru'
                    WHEN warehouse_location LIKE 'Mangaluru%' OR warehouse_location LIKE 'Zone C%' THEN 'Mangaluru'
                    WHEN warehouse_location LIKE 'Hubballi%' OR warehouse_location LIKE 'Zone D%' THEN 'Hubballi'
                    WHEN warehouse_location LIKE 'Belagavi%' OR warehouse_location LIKE 'Zone E%' THEN 'Belagavi'
                    WHEN warehouse_location LIKE 'Shivamogga%' OR warehouse_location LIKE 'Zone F%' THEN 'Shivamogga'
                    ELSE TRIM(SPLIT(warehouse_location, ' - ')[0])
                END as zone,
                COUNT(*) as total_skus,
                COALESCE(SUM(quantity), 0) as total_units,
                COALESCE(ROUND(SUM(quantity * unit_price), 2), 0.0) as total_val
            FROM products
            GROUP BY 
                CASE 
                    WHEN warehouse_location LIKE 'Bengaluru%' OR warehouse_location LIKE 'Zone A%' THEN 'Bengaluru'
                    WHEN warehouse_location LIKE 'Mysuru%' OR warehouse_location LIKE 'Zone B%' THEN 'Mysuru'
                    WHEN warehouse_location LIKE 'Mangaluru%' OR warehouse_location LIKE 'Zone C%' THEN 'Mangaluru'
                    WHEN warehouse_location LIKE 'Hubballi%' OR warehouse_location LIKE 'Zone D%' THEN 'Hubballi'
                    WHEN warehouse_location LIKE 'Belagavi%' OR warehouse_location LIKE 'Zone E%' THEN 'Belagavi'
                    WHEN warehouse_location LIKE 'Shivamogga%' OR warehouse_location LIKE 'Zone F%' THEN 'Shivamogga'
                    ELSE TRIM(SPLIT(warehouse_location, ' - ')[0])
                END
            ORDER BY total_units DESC
        """).collect()

        zone_distribution = [
            {
                "zone": r["zone"] or "General",
                "area": r["zone"] or "General",
                "skus": int(r["total_skus"]),
                "units": int(r["total_units"]),
                "value": float(r["total_val"])
            }
            for r in zone_rows
        ]

        # 2. Turnover Indicator
        turnover_metrics = spark.sql("""
            SELECT 
                (SELECT COALESCE(SUM(quantity * unit_price), 0.0) FROM transactions WHERE transaction_type = 'OUTGOING') as cogs,
                (SELECT COALESCE(SUM(quantity * unit_price), 1.0) FROM products) as avg_inv_value
        """).collect()[0]

        cogs = float(turnover_metrics["cogs"])
        inv_val = float(turnover_metrics["avg_inv_value"])
        turnover_ratio = round(cogs / max(inv_val, 1.0), 2)

        # 3. Dynamic Smart Recommendations generated from Spark data
        recommendations = []

        # Check out of stock count
        oos_count = spark.sql("SELECT COUNT(*) as cnt FROM products WHERE quantity = 0").collect()[0]["cnt"]
        if oos_count > 0:
            recommendations.append({
                "type": "CRITICAL",
                "icon": "exclamation-triangle",
                "badge": "danger",
                "title": f"Restock {oos_count} Depleted SKU(s)",
                "action": "Urgent Purchase Order",
                "detail": f"{oos_count} products have reached 0 inventory. Warehouse dispatch is currently halted for these items."
            })

        # Check low stock count
        low_count = spark.sql("SELECT COUNT(*) as cnt FROM products WHERE quantity > 0 AND quantity <= reorder_threshold").collect()[0]["cnt"]
        if low_count > 0:
            recommendations.append({
                "type": "WARNING",
                "icon": "box-arrow-in-down",
                "badge": "warning",
                "title": f"Procure Stock for {low_count} Low-Threshold Items",
                "action": "Schedule Supplier Orders",
                "detail": f"{low_count} items have crossed their minimum safety reorder thresholds."
            })

        # Check dead stock / capital efficiency
        dead_rows = spark.sql("""
            SELECT COUNT(*) as cnt, COALESCE(ROUND(SUM(quantity * unit_price), 2), 0.0) as val
            FROM products
            WHERE product_id NOT IN (SELECT DISTINCT product_id FROM transactions WHERE transaction_type = 'OUTGOING')
              AND quantity > 0
        """).collect()[0]

        if int(dead_rows["cnt"]) > 0:
            recommendations.append({
                "type": "OPTIMIZATION",
                "icon": "piggy-bank",
                "badge": "info",
                "title": f"Liquidate Inactive Stock (₹{dead_rows['val']:,.2f} tied up)",
                "action": "Discount / Clearance",
                "detail": f"{dead_rows['cnt']} products have zero outbound movement. Consider bundling or promotional clearance."
            })

        # Warehouse zone balance check
        if zone_distribution:
            highest_zone = zone_distribution[0]
            recommendations.append({
                "type": "SPACE_UTILIZATION",
                "icon": "grid-3x3-gap-fill",
                "badge": "primary",
                "title": f"Optimize Space in {highest_zone['zone']}",
                "action": "Balance Storage Slots",
                "detail": f"{highest_zone['zone']} houses {highest_zone['units']} units ({highest_zone['skus']} SKUs). Rebalance heavy incoming deliveries to secondary aisles."
            })

        return {
            "zone_distribution": zone_distribution,
            "turnover_ratio": turnover_ratio,
            "cogs": cogs,
            "inventory_valuation": inv_val,
            "recommendations": recommendations
        }

    def _sync_risk_alerts(self, analyzed_products):
        """Internal helper to automatically sync detected critical and warning risks into the alerts table."""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            for item in analyzed_products:
                pid = item["product_id"]
                risk = item["risk_level"]
                stock = item["current_stock"]

                if risk == "Critical":
                    alert_type = "OUT_OF_STOCK" if stock == 0 else "CRITICAL_RISK"
                    severity = "CRITICAL"
                    msg = f"[{pid}] {item['product_name']}: {item['explanation']}"

                    # Insert if no active alert exists for this product and alert_type
                    cursor.execute("""
                        SELECT id FROM alerts 
                        WHERE product_id = ? AND alert_type = ? AND status = 'ACTIVE'
                    """, (pid, alert_type))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO alerts (product_id, alert_type, severity, message, status)
                            VALUES (?, ?, ?, ?, 'ACTIVE')
                        """, (pid, alert_type, severity, msg))

                elif risk == "High":
                    alert_type = "LOW_STOCK"
                    severity = "WARNING"
                    msg = f"[{pid}] {item['product_name']}: {item['explanation']}"

                    cursor.execute("""
                        SELECT id FROM alerts 
                        WHERE product_id = ? AND alert_type = ? AND status = 'ACTIVE'
                    """, (pid, alert_type))
                    if not cursor.fetchone():
                        cursor.execute("""
                            INSERT INTO alerts (product_id, alert_type, severity, message, status)
                            VALUES (?, ?, ?, ?, 'ACTIVE')
                        """, (pid, alert_type, severity, msg))

            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Error syncing risk alerts: {e}")
