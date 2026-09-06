import re

from flask import Blueprint, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, AuditLog

auth_bp = Blueprint("auth", __name__)

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
ALLOWED_ROLES = {"citizen", "officer", "verifier", "admin"}


def _log_action(user_id, action, details):
    entry = AuditLog(
        user_id=user_id,
        action=action,
        details=details,
        ip_address=request.remote_addr,
    )
    db.session.add(entry)
    db.session.commit()


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or request.form

    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    phone = (data.get("phone") or "").strip()
    role = (data.get("role") or "citizen").strip().lower()

    if not full_name or len(full_name) < 3:
        return jsonify({"error": "Full name must be at least 3 characters."}), 400
    if not EMAIL_RE.match(email):
        return jsonify({"error": "A valid email address is required."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400
    if role not in ALLOWED_ROLES:
        role = "citizen"
    # Only citizens can self-register through the public form; other roles
    # are provisioned by an administrator.
    if role != "citizen":
        role = "citizen"

    if User.query.filter_by(email=email).first():
        return jsonify({"error": "An account with this email already exists."}), 409

    user = User(
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        phone=phone,
    )
    db.session.add(user)
    db.session.commit()

    _log_action(user.id, "REGISTER", f"New {role} account registered")

    return jsonify({"message": "Registration successful. Please log in."}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or request.form
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    user = User.query.filter_by(email=email).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid email or password."}), 401

    if not user.is_active:
        return jsonify({"error": "This account has been deactivated."}), 403

    session["user_id"] = user.id
    session["role"] = user.role
    session["full_name"] = user.full_name

    _log_action(user.id, "LOGIN", "User logged in")

    redirect_map = {
        "citizen": "/citizen/dashboard",
        "officer": "/officer/dashboard",
        "verifier": "/verifier/dashboard",
        "admin": "/admin/dashboard",
    }

    return jsonify(
        {
            "message": "Login successful.",
            "role": user.role,
            "full_name": user.full_name,
            "redirect": redirect_map.get(user.role, "/"),
        }
    ), 200


@auth_bp.route("/logout", methods=["POST"])
def logout():
    user_id = session.get("user_id")
    if user_id:
        _log_action(user_id, "LOGOUT", "User logged out")
    session.clear()
    return jsonify({"message": "Logged out."}), 200
