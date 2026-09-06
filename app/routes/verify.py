from flask import Blueprint, render_template, request, session

from app.services.verification_service import verify_certificate

verify_bp = Blueprint("verify", __name__)


@verify_bp.route("/verify", methods=["GET"])
def verify_landing():
    return render_template("verify.html", result=None)


@verify_bp.route("/verify/<token>", methods=["GET"])
def verify_by_token(token):
    outcome = verify_certificate(
        token=token,
        method="QR_SCAN",
        verifier_id=session.get("user_id"),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    return render_template("verification_result.html", result=outcome)


@verify_bp.route("/verify/lookup", methods=["POST"])
def verify_lookup():
    certificate_number = (request.form.get("certificate_number") or "").strip()
    token = (request.form.get("token") or "").strip()

    method = "TOKEN" if token else "CERTIFICATE_NUMBER"

    outcome = verify_certificate(
        token=token or None,
        certificate_number=certificate_number or None,
        method=method,
        verifier_id=session.get("user_id"),
        ip_address=request.remote_addr,
        user_agent=request.headers.get("User-Agent"),
    )
    return render_template("verification_result.html", result=outcome)
