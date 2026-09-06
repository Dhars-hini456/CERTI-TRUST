from flask import Blueprint, request, jsonify, session

from app.utils.decorators import role_required
from app.services.verification_service import verify_certificate
from app.models import VerificationLog

verifier_bp = Blueprint("verifier", __name__)


@verifier_bp.route("/verify", methods=["POST"])
@role_required("verifier", "officer", "admin")
def verifier_verify():
    data = request.get_json(silent=True) or request.form
    token = (data.get("token") or "").strip()
    certificate_number = (data.get("certificate_number") or "").strip()
    method = data.get("method", "TOKEN" if token else "CERTIFICATE_NUMBER")

    outcome = verify_certificate(
        token=token or None,
        certificate_number=certificate_number or None,
        method=method,
        verifier_id=session.get("user_id"),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )

    certificate = outcome.pop("certificate", None)
    outcome["certificate"] = (
        {
            "certificate_number": certificate.certificate_number,
            "certificate_type": certificate.certificate_type.name if certificate.certificate_type else "-",
            "applicant_name": certificate.applicant_name,
            "issue_date": certificate.issue_date,
            "expiry_date": certificate.expiry_date,
            "issued_by": certificate.issued_by,
            "status": certificate.status,
            "version_number": certificate.version_number,
        }
        if certificate
        else None
    )

    return jsonify(outcome)


@verifier_bp.route("/history", methods=["GET"])
@role_required("verifier", "officer", "admin")
def verifier_history():
    logs = (
        VerificationLog.query.filter_by(verifier_id=session["user_id"])
        .order_by(VerificationLog.timestamp.desc())
        .limit(100)
        .all()
    )
    return jsonify(
        [
            {
                "id": log.id,
                "certificate_id": log.certificate_id,
                "method": log.verification_method,
                "result": log.verification_result,
                "timestamp": log.timestamp.strftime("%d-%m-%Y %H:%M"),
            }
            for log in logs
        ]
    )
