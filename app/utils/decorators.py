from functools import wraps

from flask import redirect, session, url_for, flash, jsonify, request


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            if request.path.startswith("/api/"):
                return jsonify({"error": "Authentication required"}), 401
            flash("Please log in to continue.", "warning")
            return redirect(url_for("pages.login_page"))
        return view(*args, **kwargs)

    return wrapped


def role_required(*roles):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if "user_id" not in session:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Authentication required"}), 401
                flash("Please log in to continue.", "warning")
                return redirect(url_for("pages.login_page"))
            if session.get("role") not in roles:
                if request.path.startswith("/api/"):
                    return jsonify({"error": "Insufficient permissions"}), 403
                flash("You do not have permission to access that page.", "danger")
                return redirect(url_for("pages.dashboard_redirect"))
            return view(*args, **kwargs)

        return wrapped

    return decorator


def current_user_id():
    return session.get("user_id")


def current_role():
    return session.get("role")
