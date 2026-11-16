# An Apache Spark-Based Data Visualization Dashboard System for Warehouse Management

A complete, modern, intelligent Warehouse Management and Data Visualization System powered by **Apache Spark**, **PySpark**, **Python Flask**, **SQLite**, **Bootstrap 5**, and **Chart.js**.

---

## 📋 Project Overview & Architecture

This application provides real-time warehouse inventory monitoring, transactional velocity modeling, stock shortage prediction, and performance optimization through an executive web dashboard. 

Unlike ordinary inventory portals, **Apache Spark genuinely drives all big data transformations, time-series aggregations, depletion risk calculations, and inventory movement intelligence**.

```
[ Warehouse Data Sources ]
  - SQLite Relational Database (Products, Transactions, Alerts, Users)
  - Bulk CSV Uploads (Products & Transactions)
              │
              ▼
[ Apache Spark Analytics Engine (PySpark 4.3 + Spark SQL) ]
  - Converts tabular datasets into PySpark DataFrames with explicit schemas
  - Creates Spark SQL Temporary Views (`products`, `transactions`)
  - Computes Window Functions, Percentiles, and Running Consumption Averages
  - Evaluates Depletion Runway: Days = Current Stock / (30-Day Outflow / 30)
  - Classifies Risk Tiers: Critical (<3d), High (<14d), Moderate (<30d), Healthy (30d+)
  - Detects Velocity Profiles: Fast-Moving, Slow-Moving, Dead Stock, Outflow Anomalies
  - Calculates Storage Zone Utilization & Inventory Turnover Ratios
              │
              ▼
[ Flask REST API & Web Server ]
  - `/api/analytics/dashboard`     - Spark aggregated summary & monthly trends
  - `/api/analytics/risk`          - Spark Smart Stock Risk Assessment
  - `/api/analytics/movement`      - Spark Inventory Movement Intelligence
  - `/api/analytics/performance`   - Spark Performance Insights & Recommendations
  - `/api/products` & `/api/transactions` - Live CRUD & inventory mutations
  - `/api/upload/*`                - Validated bulk CSV ingestion pipeline
  - `/api/export/*`                - Instant downloadable CSV reports
              │
              ▼
[ Responsive Interactive Dashboard ]
  - Bootstrap 5 responsive layout with navy blue (#0f172a) & teal accents (#0d9488)
  - Dynamic Chart.js 4.4 interactive charts (Doughnut, Bar, Time-series, Top-K)
  - Real-time stock movement modal & immediate inventory adjustments
  - Search, filter, pagination, and alert resolution workflow
```

---

## 🚀 Key Modules & Unique Features

### 1. Executive Dashboard
- **8 KPI Summary Cards**: Total catalog SKUs, physical stock units, total inventory valuation ($), low-stock products, out-of-stock count, incoming stock units, outgoing dispatches, and fulfilled outbound valuation.
- **Spark Live Runtime Banner**: Displays PySpark engine status, cluster master (`local[2]`), JVM execution latency in milliseconds, and last-processed timestamp.
- **Interactive Visualizations**:
  - *Monthly Stock Movement*: Grouped bar chart comparing incoming shipments vs. outbound dispatches over time.
  - *Inventory by Category*: Doughnut chart illustrating category holding valuation share.
  - *Top-Moving Products*: Horizontal bar chart ranking high-demand products by dispatched volume.
  - *Low-Stock Table*: Highlights items at or below reorder thresholds.
  - *Recent Activity Feed*: Live transactional audit feed with color-coded badges.

### 2. User Authentication & Profile
- Secure session-based authentication with `werkzeug.security` password hashing.
- Default Administrator account pre-seeded for immediate evaluation:
  - **Username/Email**: `admin@warehouse.io`
  - **Password**: `admin123`
- Full Administrator registration workflow (`/register`).
- Administrator Profile page (`/profile`) with credential updates, security audit trail, and JVM runtime diagnostics.

### 3. Inventory Master Management
- Complete catalog CRUD interface: Add, Edit, Delete, and Inspect products.
- Product fields: Product ID / SKU, Product Name, Category, Available Quantity, Unit Price, Supplier, Warehouse Location (Zone / Aisle / Bin), and Reorder Threshold.
- Real-time stock transaction modal: record `INCOMING` shipments, `OUTGOING` customer dispatches, or `ADJUSTMENT` audits with instantaneous quantity reconciliation and insufficient stock safeguards.
- Multi-parameter live search and category/status filtering.

### 4. Unique Feature: Smart Stock Risk Analysis (`/risk-analysis`)
- Employs PySpark SQL and DataFrame transformations to calculate continuous consumption velocity:
  $$\text{Daily Burn Rate} = \frac{\sum \text{Outflow}_{30\text{d}}}{30}$$
  $$\text{Estimated Days to Depletion} = \frac{\text{Current Available Stock}}{\text{Daily Burn Rate}}$$
- **Risk Levels Assigned**:
  - 🔴 **Critical**: 0 stock or depletion in $< 3$ days.
  - 🟡 **High**: Stock $\le$ reorder threshold or depletion in $< 14$ days.
  - 🔵 **Moderate**: Stock depletion in $14$ to $30$ days.
  - 🟢 **Healthy**: Safe inventory buffer exceeding $30+$ days.
- **Plain-English Explanations**: Provides data-backed explanations for every item (e.g., *"Severe depletion risk: 3 units remaining against 1.9 units/day burn rate. Stock will be exhausted in ~1.6 days."*).

### 5. Unique Feature: Inventory Movement Intelligence (`/movement-intelligence`)
- **Velocity Classifier**:
  - *Fast-Moving*: High-velocity SKUs with frequent outbound turnover.
  - *Slow-Moving*: Subdued turnover with stagnant stock in storage.
  - *Dead Stock (Non-Moving)*: Zero outbound movements recorded; computes capital tied up in dormant inventory.
- **Anomaly Detection**: Flags sudden demand spikes where a single dispatch exceeds 2.5× the product's historical average order size.
- **Category Demand Momentum**: Compares outbound volume and valuation across product categories.

### 6. Unique Feature: Warehouse Performance Insights (`/performance`)
- **Storage Zone Distribution**: Visualizes physical stored units and capital allocation across warehouse zones (Zone A through Zone F).
- **Inventory Turnover Ratio**: Evaluates fulfillment velocity relative to holding valuation:
  $$\text{Turnover Ratio} = \frac{\text{Cost of Goods Outbound}}{\text{Holding Valuation}}$$
- **Automated Recommendations**: Generates action items based on live Spark metrics (e.g., restocking depleted items, liquidating inactive stock, rebalancing overloaded storage aisles).

### 7. Alerts & Notifications Management (`/alerts`)
- Automated alert triggers generated when items breach safety thresholds, run out of stock, or display critical depletion risks.
- Filter alerts by status (`ACTIVE`, `RESOLVED`) and severity (`CRITICAL`, `WARNING`).
- Individual and bulk *"Resolve All"* workflow with administrator audit tagging.

### 8. Reports & Data Export (`/reports`)
- Instant one-click CSV export:
  - `warehouse_inventory_YYYYMMDD.csv`
  - `stock_risk_assessment_YYYYMMDD.csv`
  - `warehouse_transactions_YYYYMMDD.csv`
  - `category_performance_YYYYMMDD.csv`
- Previews category summaries and monthly trend tables.

### 9. Bulk CSV Data Ingestion & Demo Data Manager (`/data-management`)
- **Bulk Products Ingestion**: Validates CSV column headers, data types, and updates existing records.
- **Bulk Transactions Ingestion**: Ingests movements and recalculates inventory levels.
- **Downloadable Sample CSVs**: Ready-to-use sample templates (`sample_products.csv`, `sample_transactions.csv`).
- **One-Click Demo Reset**: Instantly resets the warehouse with 44 diverse products across 6 industries and 230+ realistic historical transactions.

---

## 🛠️ Technology Stack

| Layer | Technologies |
|---|---|
| **Big Data Engine** | Apache Spark 4.3, PySpark, Spark SQL, Py4J |
| **Backend Web Server** | Python 3.11, Flask 3.1, Werkzeug (Security) |
| **Database** | SQLite (Zero-config, ACID-compliant relational storage) |
| **Data Manipulation** | Pandas, PySpark DataFrames |
| **Frontend Framework** | HTML5, CSS3, JavaScript (ES6+), Bootstrap 5.3 |
| **Visualizations** | Chart.js 4.4, Bootstrap Icons 1.11 |

---

## ⚙️ Installation & Execution Instructions

### Prerequisites
1. **Java Development Kit**: JDK 17, 21, or 25 (e.g., `C:\Program Files\Java\jdk-21.0.12`).
2. **Python**: Python 3.10+ (available in `backend/.venv`).

### Running the Application

1. Open PowerShell or Terminal and navigate to the project root:
   ```powershell
   cd backend
   ```

2. Activate the virtual environment or run with the project's Python:
   ```powershell
   .\.venv\Scripts\python.exe run.py
   ```

3. Open your browser and access the application:
   ```
   http://127.0.0.1:5000
   ```

4. Sign in with the default Administrator credentials:
   - **Email / Username**: `admin@warehouse.io`
   - **Password**: `admin123`

---

## 🧪 Automated Testing & Verification

The project includes an end-to-end test suite (`tests/test_warehouse_spark.py`) validating all 10 core functional areas:

```powershell
cd backend
.\.venv\Scripts\python.exe -m unittest tests/test_warehouse_spark.py
```

### Verified Test Cases:
1. `test_01_authentication`: Admin login, session validation, route protection.
2. `test_02_product_crud`: Product creation, retrieval, updates, and deletion.
3. `test_03_stock_transaction`: Inbound/outbound movements and stock balance guardrails.
4. `test_04_spark_analytics_engine`: PySpark DataFrame creation, temp views, and SQL aggregations.
5. `test_05_smart_stock_risk_analysis`: Depletion runway calculation and risk classification.
6. `test_06_movement_intelligence`: Fast-moving, slow-moving, dead stock, and anomaly detection.
7. `test_07_warehouse_performance`: Zone distribution, turnover ratios, and dynamic recommendations.
8. `test_08_alerts_management`: Incident generation, filtering, and resolution.
9. `test_09_csv_bulk_upload_validation`: CSV schema validation and bulk database ingestion.
10. `test_10_csv_report_exports`: Downloadable CSV generation for all reports.

---

## 📁 Project Structure

```
├── backend/
│   ├── app/
│   │   ├── __init__.py           # Flask app factory & configuration
│   │   ├── database.py           # SQLite connection, schema & activity logs
│   │   ├── spark_engine.py       # Apache Spark & PySpark analytics core
│   │   ├── auth.py               # Authentication decorators & helpers
│   │   ├── seed_data.py          # Realistic demo dataset & CSV generator
│   │   ├── routes/
│   │   │   ├── __init__.py
│   │   │   ├── api.py            # REST API endpoints for Spark & CRUD
│   │   │   └── views.py          # Page routes & template rendering
│   │   ├── static/
│   │   │   ├── css/
│   │   │   │   └── dashboard.css # Navy, white & teal theme styling
│   │   │   └── js/
│   │   │       ├── dashboard.js  # Live KPI & Chart.js visualizations
│   │   │       └── inventory.js  # Catalog CRUD & stock movements
│   │   └── templates/
│   │       ├── base.html         # Sidebar, navbar & base skeleton
│   │       ├── login.html        # Sign in page
│   │       ├── register.html     # Administrator registration
│   │       ├── dashboard.html    # Executive dashboard
│   │       ├── inventory.html    # Product inventory management
│   │       ├── risk_analysis.html# Smart Stock Risk Analysis module
│   │       ├── movement.html     # Inventory Movement Intelligence module
│   │       ├── performance.html  # Warehouse Performance Insights module
│   │       ├── alerts.html       # Alerts & Notifications center
│   │       ├── reports.html      # Reports & CSV data export
│   │       ├── upload.html       # Bulk CSV upload & demo manager
│   │       └── profile.html      # Admin profile & Spark diagnostics
│   ├── data/
│   │   ├── warehouse.db          # SQLite database file
│   │   └── demo/                 # Downloadable sample CSV templates
│   │       ├── sample_products.csv
│   │       └── sample_transactions.csv
│   ├── tests/
│   │   └── test_warehouse_spark.py # Automated unit & integration tests
│   ├── requirements.txt          # Python dependencies
│   └── run.py                    # Application launch script
└── README.md                     # Documentation
```
