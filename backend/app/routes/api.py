import os
import csv
import io
from datetime import datetime
from flask import Blueprint, jsonify, request, session, Response
from app.database import get_db_connection, log_activity
from app.spark_engine import SparkWarehouseEngine
from app.auth import login_required, admin_required

api_bp = Blueprint('api', __name__, url_prefix='/api')

# Helper to get current username
def current_username():
    return session.get('username', 'System')

# =========================================================================
# 1. Spark Analytics Endpoints
# =========================================================================

@api_bp.route('/analytics/dashboard', methods=['GET'])
@login_required
def get_dashboard_analytics():
    """Returns genuine Apache Spark processed dashboard analytics."""
    try:
        engine = SparkWarehouseEngine.get_instance()
        data = engine.process_warehouse_analytics()
        diagnostics = engine.get_diagnostics()
        return jsonify({
            "success": True,
            "data": data,
            "spark": diagnostics
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "spark": SparkWarehouseEngine.get_instance().get_diagnostics()
        }), 500

@api_bp.route('/analytics/risk', methods=['GET'])
@admin_required
def get_stock_risk_analysis():
    """Unique Feature: Smart Stock Risk Analysis computed via PySpark (Admin Only)."""
    try:
        engine = SparkWarehouseEngine.get_instance()
        risk_data = engine.run_stock_risk_analysis()
        return jsonify({
            "success": True,
            "data": risk_data,
            "spark": engine.get_diagnostics()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/analytics/movement', methods=['GET'])
@login_required
def get_movement_intelligence():
    """Unique Feature: Inventory Movement Intelligence computed via PySpark."""
    try:
        engine = SparkWarehouseEngine.get_instance()
        data = engine.run_inventory_movement_intelligence()
        return jsonify({
            "success": True,
            "data": data,
            "spark": engine.get_diagnostics()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/analytics/performance', methods=['GET'])
@login_required
def get_warehouse_performance():
    """Unique Feature: Warehouse Performance Insights & Recommendations via Spark."""
    try:
        engine = SparkWarehouseEngine.get_instance()
        data = engine.run_warehouse_performance_insights()
        return jsonify({
            "success": True,
            "data": data,
            "spark": engine.get_diagnostics()
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@api_bp.route('/analytics/diagnostics', methods=['GET'])
@login_required
def get_spark_diagnostics():
    """Returns runtime diagnostic metrics of the PySpark Engine."""
    engine = SparkWarehouseEngine.get_instance()
    return jsonify({
        "success": True,
        "diagnostics": engine.get_diagnostics()
    })

# =========================================================================
# 2. Inventory Product CRUD Endpoints
# =========================================================================

@api_bp.route('/products', methods=['GET'])
@login_required
def list_products():
    """Retrieves products with optional search and category filters."""
    search = request.args.get('search', '').strip()
    category = request.args.get('category', '').strip()
    status_filter = request.args.get('status', '').strip()

    conn = get_db_connection()
    query = "SELECT * FROM products WHERE 1=1"
    params = []

    if search:
        query += " AND (product_id LIKE ? OR product_name LIKE ? OR supplier LIKE ? OR warehouse_location LIKE ?)"
        wildcard = f"%{search}%"
        params.extend([wildcard, wildcard, wildcard, wildcard])

    if category and category != 'All':
        query += " AND category = ?"
        params.append(category)

    if status_filter == 'OUT_OF_STOCK':
        query += " AND quantity = 0"
    elif status_filter == 'LOW_STOCK':
        query += " AND quantity > 0 AND quantity <= reorder_threshold"
    elif status_filter == 'HEALTHY':
        query += " AND quantity > reorder_threshold"

    query += " ORDER BY product_name ASC"

    rows = conn.execute(query, params).fetchall()
    products = [dict(r) for r in rows]

    # Categories list for filters
    cat_rows = conn.execute("SELECT DISTINCT category FROM products ORDER BY category ASC").fetchall()
    categories = [r['category'] for r in cat_rows]

    conn.close()
    return jsonify({
        "success": True,
        "count": len(products),
        "products": products,
        "categories": categories
    })

@api_bp.route('/products', methods=['POST'])
@admin_required
def add_product():
    """Adds a new warehouse product."""
    data = request.get_json() or {}
    product_id = data.get('product_id', '').strip()
    product_name = data.get('product_name', '').strip()
    category = data.get('category', '').strip()
    quantity = data.get('quantity', 0)
    unit_price = data.get('unit_price', 0.0)
    supplier = data.get('supplier', '').strip()
    location = data.get('warehouse_location', '').strip()
    threshold = data.get('reorder_threshold', 10)

    # Validation
    if not product_id or not product_name or not category:
        return jsonify({"success": False, "error": "Product ID, Name, and Category are required."}), 400

    try:
        quantity = int(quantity)
        unit_price = float(unit_price)
        threshold = int(threshold)
    except ValueError:
        return jsonify({"success": False, "error": "Quantity, Unit Price, and Threshold must be numbers."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO products (
                product_id, product_name, category, quantity, unit_price,
                supplier, warehouse_location, reorder_threshold
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (product_id, product_name, category, quantity, unit_price, supplier, location, threshold))

        # Record initial inventory transaction if quantity > 0
        if quantity > 0:
            cursor.execute("""
                INSERT INTO stock_transactions (
                    product_id, transaction_type, quantity, unit_price,
                    reference_no, notes
                ) VALUES (?, 'INCOMING', ?, ?, 'INITIAL-STOCK', 'Initial Stock Addition')
            """, (product_id, quantity, unit_price))

        conn.commit()
        log_activity(current_username(), "ADD_PRODUCT", f"Added {product_id} ({product_name}) with {quantity} units.")
        return jsonify({"success": True, "message": f"Product {product_id} added successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": f"Failed to save product: {str(e)}"}), 400
    finally:
        conn.close()

@api_bp.route('/products/<product_id>', methods=['GET'])
@login_required
def get_product(product_id):
    """Retrieves product details along with historical stock transactions."""
    conn = get_db_connection()
    prod = conn.execute("SELECT * FROM products WHERE product_id = ?", (product_id,)).fetchone()
    if not prod:
        conn.close()
        return jsonify({"success": False, "error": "Product not found."}), 404

    tx_rows = conn.execute("""
        SELECT * FROM stock_transactions 
        WHERE product_id = ? 
        ORDER BY transaction_date DESC 
        LIMIT 20
    """, (product_id,)).fetchall()

    product_dict = dict(prod)
    tx_list = [dict(t) for t in tx_rows]
    conn.close()

    return jsonify({
        "success": True,
        "product": product_dict,
        "transactions": tx_list
    })

@api_bp.route('/products/<product_id>', methods=['PUT'])
@admin_required
def update_product(product_id):
    """Updates an existing product."""
    data = request.get_json() or {}
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        existing = cursor.fetchone()
        if not existing:
            conn.close()
            return jsonify({"success": False, "error": "Product not found."}), 404

        name = data.get('product_name', existing['product_name']).strip()
        category = data.get('category', existing['category']).strip()
        quantity = int(data.get('quantity', existing['quantity']))
        unit_price = float(data.get('unit_price', existing['unit_price']))
        supplier = data.get('supplier', existing['supplier']).strip()
        location = data.get('warehouse_location', existing['warehouse_location']).strip()
        threshold = int(data.get('reorder_threshold', existing['reorder_threshold']))

        cursor.execute("""
            UPDATE products SET
                product_name = ?,
                category = ?,
                quantity = ?,
                unit_price = ?,
                supplier = ?,
                warehouse_location = ?,
                reorder_threshold = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE product_id = ?
        """, (name, category, quantity, unit_price, supplier, location, threshold, product_id))

        conn.commit()
        log_activity(current_username(), "UPDATE_PRODUCT", f"Updated product {product_id} ({name}).")
        return jsonify({"success": True, "message": f"Product {product_id} updated successfully."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        conn.close()

@api_bp.route('/products/<product_id>', methods=['DELETE'])
@admin_required
def delete_product(product_id):
    """Deletes a product and related records."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM stock_transactions WHERE product_id = ?", (product_id,))
        cursor.execute("DELETE FROM alerts WHERE product_id = ?", (product_id,))
        cursor.execute("DELETE FROM products WHERE product_id = ?", (product_id,))
        conn.commit()
        log_activity(current_username(), "DELETE_PRODUCT", f"Deleted product {product_id}.")
        return jsonify({"success": True, "message": f"Product {product_id} deleted."})
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        conn.close()

# =========================================================================
# 3. Stock Transactions Endpoints
# =========================================================================

@api_bp.route('/transactions', methods=['GET'])
@login_required
def list_transactions():
    """Lists stock transactions with pagination and filters."""
    limit = int(request.args.get('limit', 50))
    tx_type = request.args.get('type', '')
    product_id = request.args.get('product_id', '')

    conn = get_db_connection()
    query = """
        SELECT t.*, p.product_name, p.category 
        FROM stock_transactions t
        LEFT JOIN products p ON t.product_id = p.product_id
        WHERE 1=1
    """
    params = []
    if tx_type:
        query += " AND t.transaction_type = ?"
        params.append(tx_type)
    if product_id:
        query += " AND t.product_id = ?"
        params.append(product_id)

    query += " ORDER BY t.transaction_date DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify({
        "success": True,
        "transactions": [dict(r) for r in rows]
    })

@api_bp.route('/transactions', methods=['POST'])
@admin_required
def record_transaction():
    """
    Records an incoming or outgoing stock movement transaction and
    automatically adjusts the available product quantity in real time.
    """
    data = request.get_json() or {}
    product_id = data.get('product_id', '').strip()
    tx_type = data.get('transaction_type', '').upper().strip()
    quantity = data.get('quantity', 0)
    ref_no = data.get('reference_no', '').strip() or f"REF-{int(datetime.now().timestamp())}"
    notes = data.get('notes', '').strip()

    if not product_id or tx_type not in ['INCOMING', 'OUTGOING', 'ADJUSTMENT']:
        return jsonify({"success": False, "error": "Invalid product ID or transaction type (INCOMING/OUTGOING/ADJUSTMENT)."}), 400

    try:
        quantity = int(quantity)
        if quantity <= 0:
            return jsonify({"success": False, "error": "Transaction quantity must be greater than zero."}), 400
    except ValueError:
        return jsonify({"success": False, "error": "Quantity must be an integer."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM products WHERE product_id = ?", (product_id,))
        prod = cursor.fetchone()
        if not prod:
            conn.close()
            return jsonify({"success": False, "error": f"Product {product_id} not found."}), 404

        current_qty = prod['quantity']
        unit_price = prod['unit_price']

        # Calculate new quantity
        if tx_type == 'INCOMING':
            new_qty = current_qty + quantity
        elif tx_type == 'OUTGOING':
            if current_qty < quantity:
                conn.close()
                return jsonify({"success": False, "error": f"Insufficient stock. Available: {current_qty}, Requested: {quantity}"}), 400
            new_qty = current_qty - quantity
        else: # ADJUSTMENT (Set explicit target)
            new_qty = quantity

        # Update product quantity
        cursor.execute("UPDATE products SET quantity = ?, updated_at = CURRENT_TIMESTAMP WHERE product_id = ?", (new_qty, product_id))

        # Insert transaction record
        cursor.execute("""
            INSERT INTO stock_transactions (
                product_id, transaction_type, quantity, unit_price, reference_no, notes
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (product_id, tx_type, quantity, unit_price, ref_no, notes))

        conn.commit()
        log_activity(current_username(), "STOCK_MOVEMENT", f"{tx_type} {quantity} units for {product_id}. New stock: {new_qty}")
        return jsonify({
            "success": True,
            "message": f"Successfully processed {tx_type} of {quantity} units for {product_id}.",
            "new_quantity": new_qty
        })
    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "error": str(e)}), 400
    finally:
        conn.close()

# =========================================================================
# 4. Alerts and Notifications Endpoints
# =========================================================================

@api_bp.route('/alerts', methods=['GET'])
@login_required
def get_alerts():
    """Retrieves warehouse alerts with filtering."""
    status = request.args.get('status', 'ACTIVE')
    severity = request.args.get('severity', '')

    conn = get_db_connection()
    query = """
        SELECT a.*, p.product_name, p.category, p.quantity, p.reorder_threshold
        FROM alerts a
        LEFT JOIN products p ON a.product_id = p.product_id
        WHERE 1=1
    """
    params = []
    if status and status != 'ALL':
        query += " AND a.status = ?"
        params.append(status)
    if severity:
        query += " AND a.severity = ?"
        params.append(severity)

    query += " ORDER BY a.created_at DESC"

    rows = conn.execute(query, params).fetchall()
    alerts = [dict(r) for r in rows]

    counts = {
        "active": conn.execute("SELECT COUNT(*) FROM alerts WHERE status = 'ACTIVE'").fetchone()[0],
        "critical": conn.execute("SELECT COUNT(*) FROM alerts WHERE status = 'ACTIVE' AND severity = 'CRITICAL'").fetchone()[0],
        "warning": conn.execute("SELECT COUNT(*) FROM alerts WHERE status = 'ACTIVE' AND severity = 'WARNING'").fetchone()[0],
        "resolved": conn.execute("SELECT COUNT(*) FROM alerts WHERE status = 'RESOLVED'").fetchone()[0]
    }
    conn.close()

    return jsonify({
        "success": True,
        "alerts": alerts,
        "counts": counts
    })

@api_bp.route('/alerts/<int:alert_id>/resolve', methods=['POST'])
@admin_required
def resolve_alert(alert_id):
    """Marks a specific alert as resolved."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE alerts SET
            status = 'RESOLVED',
            resolved_at = CURRENT_TIMESTAMP,
            resolved_by = ?
        WHERE id = ?
    """, (current_username(), alert_id))
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Alert #{alert_id} resolved."})

@api_bp.route('/alerts/resolve-all', methods=['POST'])
@admin_required
def resolve_all_alerts():
    """Resolves all active warehouse alerts."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE alerts SET
            status = 'RESOLVED',
            resolved_at = CURRENT_TIMESTAMP,
            resolved_by = ?
        WHERE status = 'ACTIVE'
    """, (current_username(),))
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return jsonify({"success": True, "message": f"Resolved {count} active alerts."})

# =========================================================================
# 5. Bulk CSV Upload and Ingestion Endpoints
# =========================================================================

@api_bp.route('/upload/products', methods=['POST'])
@admin_required
def upload_products_csv():
    """Uploads and ingests bulk products from CSV with schema validation."""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({"success": False, "error": "Only CSV files are supported."}), 400

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        reader = csv.DictReader(stream)

        required_cols = {"product_id", "product_name", "category", "quantity", "unit_price", "supplier"}
        if not required_cols.issubset(set([col.strip().lower() for col in (reader.fieldnames or [])])):
            return jsonify({
                "success": False,
                "error": f"CSV is missing required headers: {list(required_cols)}"
            }), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        success_count = 0
        error_rows = []

        for idx, row in enumerate(reader, start=2):
            # Clean keys
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            pid = clean_row.get('product_id', '')
            name = clean_row.get('product_name', '')
            cat = clean_row.get('category', 'General')
            supplier = clean_row.get('supplier', 'Unknown')
            location = clean_row.get('warehouse_location', 'Bengaluru - Aisle 01')

            if not pid or not name:
                error_rows.append(f"Row {idx}: Missing product_id or product_name.")
                continue

            try:
                qty = int(clean_row.get('quantity', 0))
                price = float(clean_row.get('unit_price', 0.0))
                threshold = int(clean_row.get('reorder_threshold', 10))
            except ValueError:
                error_rows.append(f"Row {idx}: Invalid numeric format for quantity, price, or threshold.")
                continue

            cursor.execute("""
                INSERT INTO products (
                    product_id, product_name, category, quantity, unit_price,
                    supplier, warehouse_location, reorder_threshold
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(product_id) DO UPDATE SET
                    product_name = excluded.product_name,
                    category = excluded.category,
                    quantity = excluded.quantity,
                    unit_price = excluded.unit_price,
                    supplier = excluded.supplier,
                    warehouse_location = excluded.warehouse_location,
                    reorder_threshold = excluded.reorder_threshold,
                    updated_at = CURRENT_TIMESTAMP
            """, (pid, name, cat, qty, price, supplier, location, threshold))
            success_count += 1

        conn.commit()
        conn.close()
        log_activity(current_username(), "BULK_CSV_PRODUCTS", f"Processed CSV upload: {success_count} products saved.")

        return jsonify({
            "success": True,
            "imported_count": success_count,
            "errors": error_rows,
            "message": f"Successfully imported/updated {success_count} products."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to process CSV file: {str(e)}"}), 500

@api_bp.route('/upload/transactions', methods=['POST'])
@admin_required
def upload_transactions_csv():
    """Uploads and ingests bulk stock movement transactions from CSV."""
    if 'file' not in request.files:
        return jsonify({"success": False, "error": "No file uploaded."}), 400

    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({"success": False, "error": "Only CSV files are supported."}), 400

    try:
        stream = io.StringIO(file.stream.read().decode("utf-8"), newline=None)
        reader = csv.DictReader(stream)

        conn = get_db_connection()
        cursor = conn.cursor()
        success_count = 0
        error_rows = []

        for idx, row in enumerate(reader, start=2):
            clean_row = {k.strip().lower(): v.strip() for k, v in row.items() if k}
            pid = clean_row.get('product_id', '')
            tx_type = clean_row.get('transaction_type', '').upper()
            ref_no = clean_row.get('reference_no', f"CSV-{idx}")
            notes = clean_row.get('notes', 'Bulk Ingestion')

            if tx_type not in ['INCOMING', 'OUTGOING', 'ADJUSTMENT']:
                error_rows.append(f"Row {idx}: Invalid transaction_type '{tx_type}'.")
                continue

            try:
                qty = int(clean_row.get('quantity', 0))
                price = float(clean_row.get('unit_price', 0.0))
            except ValueError:
                error_rows.append(f"Row {idx}: Invalid quantity or unit_price.")
                continue

            # Check if product exists
            cursor.execute("SELECT quantity, unit_price FROM products WHERE product_id = ?", (pid,))
            prod = cursor.fetchone()
            if not prod:
                error_rows.append(f"Row {idx}: Product {pid} does not exist in inventory.")
                continue

            if price <= 0:
                price = prod['unit_price']

            curr_qty = prod['quantity']
            if tx_type == 'INCOMING':
                new_qty = curr_qty + qty
            elif tx_type == 'OUTGOING':
                new_qty = max(0, curr_qty - qty)
            else:
                new_qty = qty

            cursor.execute("UPDATE products SET quantity = ? WHERE product_id = ?", (new_qty, pid))
            cursor.execute("""
                INSERT INTO stock_transactions (
                    product_id, transaction_type, quantity, unit_price, reference_no, notes
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (pid, tx_type, qty, price, ref_no, notes))
            success_count += 1

        conn.commit()
        conn.close()
        log_activity(current_username(), "BULK_CSV_TX", f"Processed CSV transactions: {success_count} recorded.")

        return jsonify({
            "success": True,
            "imported_count": success_count,
            "errors": error_rows,
            "message": f"Successfully recorded {success_count} stock transactions."
        })
    except Exception as e:
        return jsonify({"success": False, "error": f"Failed to process CSV file: {str(e)}"}), 500

@api_bp.route('/demo/reset', methods=['POST'])
@admin_required
def reset_demo_data():
    """Resets the database with the rich demo dataset."""
    try:
        from app.seed_data import seed_database
        seed_database(reset=True)
        log_activity(current_username(), "RESET_DEMO_DATA", "Reset database with standard warehouse demo dataset.")
        return jsonify({"success": True, "message": "Warehouse database successfully reloaded with sample demo dataset."})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# =========================================================================
# 6. Report CSV Exports
# =========================================================================

@api_bp.route('/export/<report_type>', methods=['GET'])
@login_required
def export_csv_report(report_type):
    """Exports structured reports as downloadable CSV."""
    conn = get_db_connection()
    output = io.StringIO()
    writer = csv.writer(output)

    if report_type == 'inventory':
        writer.writerow([
            "Product ID", "Product Name", "Category", "Quantity",
            "Unit Price (₹)", "Total Value (₹)", "Supplier",
            "Warehouse Location", "Reorder Threshold", "Stock Status"
        ])
        rows = conn.execute("SELECT * FROM products ORDER BY category, product_name").fetchall()
        for r in rows:
            qty = r['quantity']
            thresh = r['reorder_threshold']
            val = qty * r['unit_price']
            status = "OUT OF STOCK" if qty == 0 else ("LOW STOCK" if qty <= thresh else "HEALTHY")
            writer.writerow([
                r['product_id'], r['product_name'], r['category'], qty,
                f"{r['unit_price']:.2f}", f"{val:.2f}", r['supplier'],
                r['warehouse_location'], thresh, status
            ])
        filename = f"warehouse_inventory_{datetime.now().strftime('%Y%m%d')}.csv"

    elif report_type == 'risk':
        if session.get('role') != 'Administrator':
            conn.close()
            return jsonify({"success": False, "error": "Access denied: Administrator privileges required for Stock Risk reports."}), 403

        engine = SparkWarehouseEngine.get_instance()
        risk_data = engine.run_stock_risk_analysis()
        writer.writerow([
            "Product ID", "Product Name", "Category", "Current Stock",
            "Reorder Threshold", "Historical 30D Outflow", "Avg Daily Consumption",
            "Days to Depletion", "Risk Level", "Risk Explanation", "Warehouse Location"
        ])
        for p in risk_data.get('products', []):
            writer.writerow([
                p['product_id'], p['product_name'], p['category'], p['current_stock'],
                p['reorder_threshold'], p['historical_outflow_30d'], p['avg_daily_consumption'],
                p['days_until_depletion'], p['risk_level'], p['explanation'], p['warehouse_location']
            ])
        filename = f"stock_risk_assessment_{datetime.now().strftime('%Y%m%d')}.csv"

    elif report_type == 'transactions':
        writer.writerow([
            "Transaction ID", "Date", "Product ID", "Transaction Type",
            "Quantity", "Unit Price (₹)", "Total Value (₹)", "Reference No", "Notes"
        ])
        rows = conn.execute("SELECT * FROM stock_transactions ORDER BY transaction_date DESC").fetchall()
        for r in rows:
            val = r['quantity'] * r['unit_price']
            writer.writerow([
                r['id'], r['transaction_date'], r['product_id'], r['transaction_type'],
                r['quantity'], f"{r['unit_price']:.2f}", f"{val:.2f}",
                r['reference_no'], r['notes']
            ])
        filename = f"warehouse_transactions_{datetime.now().strftime('%Y%m%d')}.csv"

    elif report_type == 'categories':
        engine = SparkWarehouseEngine.get_instance()
        data = engine.process_warehouse_analytics()
        writer.writerow([
            "Category", "Product Count", "Total Stock Units",
            "Total Valuation (₹)", "Avg Unit Price (₹)", "Low Stock Items"
        ])
        for c in data.get('categories', []):
            writer.writerow([
                c['category'], c['product_count'], c['total_units'],
                f"{c['category_value']:.2f}", f"{c['avg_price']:.2f}", c['low_stock_items']
            ])
        filename = f"category_performance_{datetime.now().strftime('%Y%m%d')}.csv"

    else:
        conn.close()
        return jsonify({"error": "Unknown report type."}), 400

    conn.close()
    output.seek(0)
    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )
