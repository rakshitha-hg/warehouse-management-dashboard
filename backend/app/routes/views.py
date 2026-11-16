import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, session, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import get_db_connection, log_activity
from app.auth import login_required, admin_required, get_current_user, is_admin
from app.spark_engine import SparkWarehouseEngine

views_bp = Blueprint('views', __name__)

@views_bp.route('/data/demo/<path:filename>')
def download_demo_file(filename):
    demo_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'demo')
    return send_from_directory(demo_dir, filename, as_attachment=True)

# =========================================================================
# 1. Landing & Role Selection Portal
# =========================================================================

@views_bp.route('/')
def index():
    """Application entry point: redirects authenticated sessions or shows landing selector."""
    if 'user_id' in session:
        if session.get('role') == 'Administrator':
            return redirect(url_for('views.dashboard_page'))
        return redirect(url_for('views.user_dashboard_page'))
    return redirect(url_for('views.landing_page'))

@views_bp.route('/landing')
def landing_page():
    """Landing page displaying two separate cards: USER and ADMIN."""
    return render_template('landing.html')

@views_bp.route('/login')
def login_redirect():
    """Convenience redirect to the role selection landing page or direct portals."""
    role = request.args.get('role', '').lower()
    if role == 'admin':
        return redirect(url_for('views.login_admin_page'))
    elif role == 'user':
        return redirect(url_for('views.enter_user'))
    return redirect(url_for('views.landing_page'))

# =========================================================================
# 2. Separate User and Admin Access Handlers
# =========================================================================

@views_bp.route('/enter/user')
def enter_user():
    """Direct one-click access to User Dashboard without authentication prompt."""
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE role = 'User' ORDER BY id ASC LIMIT 1").fetchone()
    if not user:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES ('user', 'user@warehouse.io', ?, 'Warehouse Staff Operator', 'User')
        """, (generate_password_hash('user123'),))
        conn.commit()
        user = conn.execute("SELECT * FROM users WHERE role = 'User' ORDER BY id ASC LIMIT 1").fetchone()

    session['user_id'] = user['id']
    session['username'] = user['username']
    session['full_name'] = user['full_name']
    session['role'] = 'User'
    conn.close()

    log_activity(session['username'], "USER_DIRECT_ACCESS", "Opened User Dashboard directly without login prompt.")
    next_page = request.args.get('next')
    return redirect(next_page or url_for('views.user_dashboard_page'))

@views_bp.route('/login/user', methods=['GET', 'POST'])
def login_user_page():
    """User login page removed: automatically directs into User Dashboard with zero credentials required."""
    return redirect(url_for('views.enter_user', next=request.args.get('next')))

@views_bp.route('/login/admin', methods=['GET', 'POST'])
def login_admin_page():
    """Dedicated Administrator Login Portal for Warehouse Controllers."""
    if 'user_id' in session and session.get('role') == 'Administrator':
        return redirect(url_for('views.dashboard_page'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE username = ? OR email = ?", (username, username)).fetchone()

        if user and check_password_hash(user['password_hash'], password):
            # Strict RBAC: prevent non-admins from authenticating via admin login
            if user['role'] != 'Administrator':
                conn.close()
                flash("Access Denied: This account does not possess Administrator privileges.", "danger")
                return render_template('login_admin.html')

            session['user_id'] = user['id']
            session['username'] = user['username']
            session['full_name'] = user['full_name']
            session['role'] = 'Administrator'

            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user['id'],))
            conn.commit()
            conn.close()

            log_activity(user['username'], "ADMIN_LOGIN", "Logged into warehouse administrator console.")
            flash(f"Welcome back, {user['full_name']}!", "success")
            next_page = request.args.get('next')
            return redirect(next_page or url_for('views.dashboard_page'))
        else:
            conn.close()
            flash("Invalid administrator username/email or password.", "danger")

    return render_template('login_admin.html')

@views_bp.route('/register', methods=['GET', 'POST'])
def register_page():
    """Administrator registration portal."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        email = request.form.get('email', '').strip()
        full_name = request.form.get('full_name', '').strip()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not username or not email or not password:
            flash("All fields are required.", "warning")
            return render_template('register.html')

        if password != confirm_password:
            flash("Passwords do not match.", "warning")
            return render_template('register.html')

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id FROM users WHERE username = ? OR email = ?", (username, email))
        if cursor.fetchone():
            conn.close()
            flash("Username or Email already registered.", "danger")
            return render_template('register.html')

        hashed_pw = generate_password_hash(password)
        cursor.execute("""
            INSERT INTO users (username, email, password_hash, full_name, role)
            VALUES (?, ?, ?, ?, 'Administrator')
        """, (username, email, hashed_pw, full_name or username))
        conn.commit()
        conn.close()

        log_activity(username, "REGISTER", "New administrator account created.")
        flash("Registration successful! Please log in as Administrator.", "success")
        return redirect(url_for('views.login_admin_page'))

    return render_template('register.html')

@views_bp.route('/logout')
def logout():
    """Clears user session and redirects to the landing page."""
    username = session.get('username', 'User')
    log_activity(username, "LOGOUT", "Signed out of warehouse dashboard.")
    session.clear()
    flash("You have been signed out successfully.", "info")
    return redirect(url_for('views.landing_page'))

# =========================================================================
# 3. Dashboards (Admin Dashboard vs User Dashboard)
# =========================================================================

@views_bp.route('/dashboard')
@admin_required
def dashboard_page():
    """Admin Dashboard: Full privileges, CRUD, CSV ingestion, alerts resolution."""
    user = get_current_user()
    engine = SparkWarehouseEngine.get_instance()
    diagnostics = engine.get_diagnostics()
    return render_template('dashboard.html', user=user, spark=diagnostics, active_page='dashboard')

@views_bp.route('/user/dashboard')
def user_dashboard_page():
    """User Dashboard: Read-only operational overview with live Spark analytics.
    Directly opens without requiring any username, user ID, or password."""
    if 'user_id' not in session:
        conn = get_db_connection()
        user = conn.execute("SELECT * FROM users WHERE role = 'User' ORDER BY id ASC LIMIT 1").fetchone()
        if not user:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO users (username, email, password_hash, full_name, role)
                VALUES ('user', 'user@warehouse.io', ?, 'Warehouse Operations Staff', 'User')
            """, (generate_password_hash('user123'),))
            conn.commit()
            user = conn.execute("SELECT * FROM users WHERE role = 'User' ORDER BY id ASC LIMIT 1").fetchone()

        session['user_id'] = user['id']
        session['username'] = user['username']
        session['full_name'] = user['full_name']
        session['role'] = 'User'
        conn.close()
        log_activity(session['username'], "USER_DIRECT_ACCESS", "Accessed User Dashboard directly.")

    user = get_current_user()
    engine = SparkWarehouseEngine.get_instance()
    diagnostics = engine.get_diagnostics()
    return render_template('user_dashboard.html', user=user, spark=diagnostics, active_page='user_dashboard')

# =========================================================================
# 4. Warehouse Modules (Role-Aware)
# =========================================================================

@views_bp.route('/inventory')
@login_required
def inventory_page():
    """Inventory Catalog: Accessible to all logged in users. Write actions restricted to Admin."""
    user = get_current_user()
    return render_template('inventory.html', user=user, active_page='inventory')

@views_bp.route('/risk-analysis')
@admin_required
def risk_analysis_page():
    """Smart Stock Risk Analysis: Strictly Administrator only."""
    user = get_current_user()
    return render_template('risk_analysis.html', user=user, active_page='risk_analysis')

@views_bp.route('/movement-intelligence')
@login_required
def movement_page():
    """Inventory Movement Intelligence: Viewable by both User and Admin."""
    user = get_current_user()
    return render_template('movement.html', user=user, active_page='movement')

@views_bp.route('/performance')
@login_required
def performance_page():
    """Warehouse Performance Insights: Viewable by both User and Admin."""
    user = get_current_user()
    return render_template('performance.html', user=user, active_page='performance')

@views_bp.route('/alerts')
@login_required
def alerts_page():
    """Warehouse Alerts: Viewable by both. Resolving alerts restricted to Admin."""
    user = get_current_user()
    return render_template('alerts.html', user=user, active_page='alerts')

@views_bp.route('/reports')
@login_required
def reports_page():
    """Warehouse Reports: Viewable and downloadable by both User and Admin."""
    user = get_current_user()
    return render_template('reports.html', user=user, active_page='reports')

# =========================================================================
# 5. Admin-Only Features
# =========================================================================

@views_bp.route('/data-management')
@admin_required
def upload_page():
    """Data Management & CSV Ingestion: Strictly Administrator only."""
    user = get_current_user()
    return render_template('upload.html', user=user, active_page='data_management')

@views_bp.route('/profile', methods=['GET', 'POST'])
@admin_required
def profile_page():
    """Administrator Profile & Spark Cluster diagnostics: Strictly Administrator only."""
    user = get_current_user()
    conn = get_db_connection()

    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip()
        new_pw = request.form.get('new_password', '').strip()

        if new_pw:
            hashed_pw = generate_password_hash(new_pw)
            conn.execute("UPDATE users SET full_name = ?, email = ?, password_hash = ? WHERE id = ?",
                         (full_name, email, hashed_pw, user['id']))
        else:
            conn.execute("UPDATE users SET full_name = ?, email = ? WHERE id = ?",
                         (full_name, email, user['id']))

        conn.commit()
        session['full_name'] = full_name
        flash("Profile updated successfully.", "success")
        log_activity(user['username'], "PROFILE_UPDATE", "Updated profile details.")
        return redirect(url_for('views.profile_page'))

    activities = conn.execute("SELECT * FROM activity_logs ORDER BY created_at DESC LIMIT 15").fetchall()
    conn.close()

    engine = SparkWarehouseEngine.get_instance()
    diagnostics = engine.get_diagnostics()

    return render_template('profile.html', user=user, activities=activities, spark=diagnostics, active_page='profile')
