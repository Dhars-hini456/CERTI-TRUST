from flask import Blueprint, request, jsonify
from werkzeug.security import generate_password_hash

from app.extensions import db
from app.models import User, Department, CertificateType, Certificate, FraudAlert
from app.utils.decorators import role_required

admin_bp = Blueprint("admin", __name__)


@admin_bp.route("/users", methods=["GET"])
@role_required("admin")
def list_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": u.id,
                "full_name": u.full_name,
                "email": u.email,
                "role": u.role,
                "department": u.department,
                "is_active": u.is_active,
            }
            for u in users
        ]
    )


@admin_bp.route("/users", methods=["POST"])
@role_required("admin")
def create_user():
    data = request.get_json(silent=True) or request.form
    full_name = (data.get("full_name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    role = (data.get("role") or "officer").strip().lower()
    department = (data.get("department") or "").strip()

    if not full_name or not email or len(password) < 6:
        return jsonify({"error": "Full name, email and a 6+ character password are required."}), 400
    if role not in ("citizen", "officer", "verifier", "admin"):
        return jsonify({"error": "Invalid role."}), 400
    if User.query.filter_by(email=email).first():
        return jsonify({"error": "Email already in use."}), 409

    user = User(
        full_name=full_name,
        email=email,
        password_hash=generate_password_hash(password),
        role=role,
        department=department,
    )
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User created.", "id": user.id}), 201


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@role_required("admin")
def toggle_user_active(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = not user.is_active
    db.session.add(user)
    db.session.commit()
    return jsonify({"message": "User status updated.", "is_active": user.is_active})


@admin_bp.route("/departments", methods=["GET"])
@role_required("admin")
def list_departments():
    depts = Department.query.all()
    return jsonify([{"id": d.id, "name": d.name, "code": d.code} for d in depts])


@admin_bp.route("/departments", methods=["POST"])
@role_required("admin")
def create_department():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()
    if not name or not code:
        return jsonify({"error": "Name and code are required."}), 400
    if Department.query.filter_by(code=code).first():
        return jsonify({"error": "Department code already exists."}), 409
    dept = Department(name=name, code=code, description=data.get("description", ""))
    db.session.add(dept)
    db.session.commit()
    return jsonify({"message": "Department created.", "id": dept.id}), 201


@admin_bp.route("/certificate-types", methods=["GET"])
@role_required("admin", "citizen", "officer", "verifier")
def list_certificate_types():
    types = CertificateType.query.all()
    return jsonify(
        [
            {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "department": t.department,
                "validity_days": t.validity_days,
                "is_active": t.is_active,
            }
            for t in types
        ]
    )


@admin_bp.route("/certificate-types", methods=["POST"])
@role_required("admin")
def create_certificate_type():
    data = request.get_json(silent=True) or request.form
    name = (data.get("name") or "").strip()
    code = (data.get("code") or "").strip().upper()
    department = (data.get("department") or "").strip()
    validity_days = int(data.get("validity_days") or 365)

    if not name or not code:
        return jsonify({"error": "Name and code are required."}), 400
    if CertificateType.query.filter_by(code=code).first():
        return jsonify({"error": "Certificate type code already exists."}), 409

    cert_type = CertificateType(
        name=name, code=code, department=department, validity_days=validity_days,
        description=data.get("description", ""),
    )
    db.session.add(cert_type)
    db.session.commit()
    return jsonify({"message": "Certificate type created.", "id": cert_type.id}), 201


@admin_bp.route("/certificates", methods=["GET"])
@role_required("admin")
def all_certificates():
    certs = Certificate.query.order_by(Certificate.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": c.id,
                "certificate_number": c.certificate_number,
                "applicant_name": c.applicant_name,
                "status": c.status,
                "version_number": c.version_number,
            }
            for c in certs
        ]
    )


@admin_bp.route("/fraud-alerts", methods=["GET"])
@role_required("admin", "officer")
def fraud_alerts():
    alerts = FraudAlert.query.order_by(FraudAlert.detected_at.desc()).limit(200).all()
    return jsonify(
        [
            {
                "id": a.id,
                "certificate_id": a.certificate_id,
                "alert_type": a.alert_type,
                "severity": a.severity,
                "reason": a.reason,
                "detected_at": a.detected_at.strftime("%d-%m-%Y %H:%M"),
                "resolved": a.resolved,
            }
            for a in alerts
        ]
    )


@admin_bp.route("/fraud-alerts/<int:alert_id>/resolve", methods=["POST"])
@role_required("admin", "officer")
def resolve_alert(alert_id):
    from flask import session

    alert = FraudAlert.query.get_or_404(alert_id)
    alert.resolved = True
    alert.resolved_by = session["user_id"]
    db.session.add(alert)
    db.session.commit()
    return jsonify({"message": "Alert marked as resolved."})
