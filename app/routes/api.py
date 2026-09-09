from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, session
from sqlalchemy import func

from app.extensions import db
from app.models import (
    Certificate, Application, VerificationLog, FraudAlert, CertificateType,
    Notification, Department,
)
from app.utils.decorators import login_required, role_required
from app.services.verification_service import verify_certificate

api_bp = Blueprint("api", __name__)


@api_bp.route("/public-stats", methods=["GET"])
def public_stats():
    """Non-sensitive, aggregate-only counts for the public landing page."""
    return jsonify(
        {
            "total_certificates": Certificate.query.count(),
            "total_verification_requests": VerificationLog.query.count(),
            "certificate_types": CertificateType.query.filter_by(is_active=True).count(),
            "departments": Department.query.count(),
        }
    )


@api_bp.route("/verify/<token>", methods=["GET"])
def api_verify_token(token):
    outcome = verify_certificate(
        token=token,
        method="TOKEN",
        verifier_id=session.get("user_id"),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    certificate = outcome.pop("certificate", None)
    outcome["certificate"] = _serialize_certificate(certificate) if certificate else None
    return jsonify(outcome)


@api_bp.route("/verify/certificate-number", methods=["POST"])
def api_verify_certificate_number():
    data = request.get_json(silent=True) or request.form
    certificate_number = (data.get("certificate_number") or "").strip()
    if not certificate_number:
        return jsonify({"error": "certificate_number is required."}), 400

    outcome = verify_certificate(
        certificate_number=certificate_number,
        method="CERTIFICATE_NUMBER",
        verifier_id=session.get("user_id"),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    certificate = outcome.pop("certificate", None)
    outcome["certificate"] = _serialize_certificate(certificate) if certificate else None
    return jsonify(outcome)


def _serialize_certificate(c):
    return {
        "id": c.id,
        "certificate_number": c.certificate_number,
        "certificate_type": c.certificate_type.name if c.certificate_type else "-",
        "applicant_name": c.applicant_name,
        "issue_date": c.issue_date,
        "expiry_date": c.expiry_date,
        "issued_by": c.issued_by,
        "status": c.status,
        "version_number": c.version_number,
    }


@api_bp.route("/dashboard", methods=["GET"])
@login_required
def dashboard_stats():
    today = datetime.utcnow().date()
    today_start = datetime(today.year, today.month, today.day)
    tomorrow_start = today_start + timedelta(days=1)
    total_certificates = Certificate.query.count()
    issued_today = Certificate.query.filter(
        Certificate.created_at >= today_start,
        Certificate.created_at < tomorrow_start,
    ).count()
    verified = Certificate.query.filter_by(status="ACTIVE").count()
    pending_applications = Application.query.filter(
        Application.status.in_(["SUBMITTED", "UNDER_REVIEW"])
    ).count()
    reissued = Certificate.query.filter(Certificate.version_number > 1).count()
    revoked = Certificate.query.filter_by(status="REVOKED").count()
    expired = Certificate.query.filter_by(status="EXPIRED").count()
    suspicious = FraudAlert.query.filter_by(resolved=False).count()
    total_verification_requests = VerificationLog.query.count()

    return jsonify(
        {
            "total_certificates": total_certificates,
            "issued_today": issued_today,
            "verified_certificates": verified,
            "pending_applications": pending_applications,
            "reissued_certificates": reissued,
            "revoked_certificates": revoked,
            "expired_certificates": expired,
            "suspicious_certificates": suspicious,
            "total_verification_requests": total_verification_requests,
        }
    )


@api_bp.route("/analytics", methods=["GET"])
@login_required
def analytics():
    # Certificates issued by month (last 6 months)
    months = []
    counts = []
    now = datetime.utcnow()
    for i in range(5, -1, -1):
        year = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year -= 1
        month_start = datetime(year, month, 1)
        if month == 12:
            next_month_start = datetime(year + 1, 1, 1)
        else:
            next_month_start = datetime(year, month + 1, 1)

        label = month_start.strftime("%b %Y")
        months.append(label)
        count = Certificate.query.filter(
            Certificate.created_at >= month_start,
            Certificate.created_at < next_month_start,
        ).count()
        counts.append(count)

    # Verification results breakdown
    result_rows = (
        db.session.query(VerificationLog.verification_result, func.count(VerificationLog.id))
        .group_by(VerificationLog.verification_result)
        .all()
    )
    verification_results = {row[0]: row[1] for row in result_rows}

    # Certificate types distribution
    type_rows = (
        db.session.query(CertificateType.name, func.count(Certificate.id))
        .join(Certificate, Certificate.certificate_type_id == CertificateType.id)
        .group_by(CertificateType.name)
        .all()
    )
    certificate_types = {row[0]: row[1] for row in type_rows}

    # Department-wise stats
    dept_rows = (
        db.session.query(Certificate.department, func.count(Certificate.id))
        .group_by(Certificate.department)
        .all()
    )
    departments = {row[0] or "Unassigned": row[1] for row in dept_rows}

    # Suspicious verification trend (alerts per day, last 7 days)
    alert_days = []
    alert_counts = []
    for i in range(6, -1, -1):
        day = (datetime.utcnow() - timedelta(days=i)).date()
        day_start = datetime(day.year, day.month, day.day)
        day_end = day_start + timedelta(days=1)
        alert_days.append(day.strftime("%d %b"))
        alert_counts.append(
            FraudAlert.query.filter(
                FraudAlert.detected_at >= day_start,
                FraudAlert.detected_at < day_end,
            ).count()
        )

    # Application status distribution
    app_status_rows = (
        db.session.query(Application.status, func.count(Application.id))
        .group_by(Application.status)
        .all()
    )
    application_status = {row[0]: row[1] for row in app_status_rows}

    return jsonify(
        {
            "certificates_by_month": {"labels": months, "values": counts},
            "verification_results": verification_results,
            "certificate_types": certificate_types,
            "departments": departments,
            "suspicious_trend": {"labels": alert_days, "values": alert_counts},
            "application_status": application_status,
        }
    )


@api_bp.route("/verification-logs", methods=["GET"])
@role_required("officer", "admin", "verifier")
def verification_logs():
    logs = VerificationLog.query.order_by(VerificationLog.timestamp.desc()).limit(300).all()
    return jsonify(
        [
            {
                "id": log.id,
                "certificate_id": log.certificate_id,
                "certificate_number": log.certificate.certificate_number if log.certificate else "-",
                "verifier": log.verifier.full_name if log.verifier_id and log.verifier else "Anonymous / Public",
                "method": log.verification_method,
                "result": log.verification_result,
                "ip_address": log.ip_address,
                "timestamp": log.timestamp.strftime("%d-%m-%Y %H:%M"),
            }
            for log in logs
        ]
    )


@api_bp.route("/notifications", methods=["GET"])
@login_required
def notifications():
    items = (
        Notification.query.filter_by(user_id=session["user_id"])
        .order_by(Notification.created_at.desc())
        .limit(20)
        .all()
    )
    return jsonify(
        [
            {
                "id": n.id,
                "title": n.title,
                "message": n.message,
                "is_read": n.is_read,
                "created_at": n.created_at.strftime("%d-%m-%Y %H:%M"),
            }
            for n in items
        ]
    )


@api_bp.route("/notifications/<int:notification_id>/read", methods=["POST"])
@login_required
def mark_notification_read(notification_id):
    notif = Notification.query.get_or_404(notification_id)
    if notif.user_id != session["user_id"]:
        return jsonify({"error": "Not authorized."}), 403
    notif.is_read = True
    db.session.add(notif)
    db.session.commit()
    return jsonify({"message": "Marked as read."})


@api_bp.route("/certificates/<int:certificate_id>", methods=["GET"])
@login_required
def get_certificate(certificate_id):
    c = Certificate.query.get_or_404(certificate_id)
    return jsonify(_serialize_certificate(c))
