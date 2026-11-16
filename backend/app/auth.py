from functools import wraps
from flask import session, redirect, url_for, flash, request, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from app.database import get_db_connection, log_activity

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Authentication required. Please log in."}), 401
            # User portal has frictionless direct access; route through enter_user to establish session
            return redirect(url_for('views.enter_user', next=request.url))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Authentication required. Please log in as Administrator."}), 401
            flash("Administrator login required. Please enter Admin credentials.", "warning")
            return redirect(url_for('views.login_admin_page', next=request.url))
        
        if session.get('role') != 'Administrator':
            if request.path.startswith('/api/'):
                return jsonify({"success": False, "error": "Access denied: Administrator privileges required."}), 403
            flash("Access denied: You do not have administrator permissions to access that page.", "danger")
            return redirect(url_for('views.user_dashboard_page'))
            
        return f(*args, **kwargs)
    return decorated_function

def get_current_user():
    """Retrieves the current authenticated user record."""
    if 'user_id' not in session:
        return None
    conn = get_db_connection()
    user = conn.execute("SELECT * FROM users WHERE id = ?", (session['user_id'],)).fetchone()
    conn.close()
    return user

def is_admin():
    """Checks whether the currently logged in user is an Administrator."""
    return session.get('role') == 'Administrator'
