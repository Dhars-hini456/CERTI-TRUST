import os

from flask import Blueprint, request, jsonify, session, current_app, send_file

from app.extensions import db
from app.models import Application, Certificate, User, Notification
from app.utils.decorators import role_required
from app.services.certificate_service import issue_certificate, reissue_certificate, revoke_certificate
from app.utils.pdf_util import generate_certificate_pdf

officer_bp = Blueprint("officer", __name__)


@officer_bp.route("/applications", methods=["GET"])
@role_required("officer", "admin")
def list_applications():
    status_filter = request.args.get("status")
    query = Application.query
    if status_filter:
        query = query.filter_by(status=status_filter)
    apps = query.order_by(Application.created_at.desc()).all()
    return jsonify(
        [
            {
                "id": a.id,
                "application_number": a.application_number,
                "citizen_name": a.citizen.full_name if a.citizen else "-",
                "certificate_type": a.certificate_type.name if a.certificate_type else "-",
                "status": a.status,
                "created_at": a.created_at.strftime("%d-%m-%Y %H:%M"),
            }
            for a in apps
        ]
    )


@officer_bp.route("/applications/<int:application_id>/approve", methods=["POST"])
@role_required("officer", "admin")
def approve_application(application_id):
    application = Application.query.get_or_404(application_id)
    if application.status not in ("SUBMITTED", "UNDER_REVIEW"):
        return jsonify({"error": "Application is not in a reviewable state."}), 400

    application.status = "APPROVED"
    application.assigned_officer_id = session["user_id"]
    db.session.add(application)
    db.session.commit()

    db.session.add(
        Notification(
            user_id=application.citizen_id,
            title="Application Approved",
            message=f"Your application {application.application_number} has been approved.",
        )
    )
    db.session.commit()

    return jsonify({"message": "Application approved."}), 200


@officer_bp.route("/applications/<int:application_id>/reject", methods=["POST"])
@role_required("officer", "admin")
def reject_application(application_id):
    data = request.get_json(silent=True) or request.form
    reason = (data.get("reason") or "Documents incomplete or invalid.").strip()

    application = Application.query.get_or_404(application_id)
    if application.status not in ("SUBMITTED", "UNDER_REVIEW"):
        return jsonify({"error": "Application is not in a reviewable state."}), 400

    application.status = "REJECTED"
    application.rejection_reason = reason
    application.assigned_officer_id = session["user_id"]
    db.session.add(application)
    db.session.commit()

    db.session.add(
        Notification(
            user_id=application.citizen_id,
            title="Application Rejected",
            message=f"Your application {application.application_number} was rejected. Reason: {reason}",
        )
    )
    db.session.commit()

    return jsonify({"message": "Application rejected."}), 200


@officer_bp.route("/applications/<int:application_id>/issue", methods=["POST"])
@role_required("officer", "admin")
def issue_certificate_route(application_id):
    application = Application.query.get_or_404(application_id)
    if application.status != "APPROVED":
        return jsonify({"error": "Application must be approved before issuing a certificate."}), 400

    officer = User.query.get(session["user_id"])
    department = officer.department or (application.certificate_type.department if application.certificate_type else "Government Department")

    certificate = issue_certificate(
        certificate_type=application.certificate_type,
        applicant_name=application.applicant_name,
        applicant_id=f"CIT-{application.citizen_id:05d}",
        date_of_birth=application.date_of_birth,
        address=application.address,
        issued_by=department,
        officer_id=officer.id,
        department=department,
        application_id=application.id,
        is_demo_data=True,
    )

    application.status = "ISSUED"
    db.session.add(application)
    db.session.commit()

    qr_path = os.path.join(current_app.config["QR_FOLDER"], f"{certificate.qr_token}.png")
    generate_certificate_pdf(certificate, qr_path, current_app.config["CERT_FOLDER"])

    db.session.add(
        Notification(
            user_id=application.citizen_id,
            title="Certificate Issued",
            message=f"Certificate {certificate.certificate_number} has been issued and digitally signed.",
        )
    )
    db.session.commit()

    return jsonify(
        {
            "message": "Certificate issued successfully.",
            "certificate_id": certificate.id,
            "certificate_number": certificate.certificate_number,
        }
    ), 201


@officer_bp.route("/certificates/<int:certificate_id>/reissue", methods=["POST"])
@role_required("officer", "admin")
def reissue_certificate_route(certificate_id):
    data = request.get_json(silent=True) or request.form
    reason = (data.get("reason") or "Citizen requested official duplicate copy.").strip()

    certificate = Certificate.query.get_or_404(certificate_id)
    if certificate.status not in ("ACTIVE",):
        return jsonify({"error": "Only an active certificate can be reissued."}), 400

    new_cert = reissue_certificate(certificate, reason, session["user_id"])

    qr_path = os.path.join(current_app.config["QR_FOLDER"], f"{new_cert.qr_token}.png")
    generate_certificate_pdf(new_cert, qr_path, current_app.config["CERT_FOLDER"])

    return jsonify(
        {
            "message": "Official reissue created.",
            "certificate_id": new_cert.id,
            "certificate_number": new_cert.certificate_number,
            "version_number": new_cert.version_number,
        }
    ), 201


@officer_bp.route("/certificates/<int:certificate_id>/revoke", methods=["POST"])
@role_required("officer", "admin")
def revoke_certificate_route(certificate_id):
    data = request.get_json(silent=True) or request.form
    reason = (data.get("reason") or "Revoked by issuing department.").strip()

    certificate = Certificate.query.get_or_404(certificate_id)
    if certificate.status == "REVOKED":
        return jsonify({"error": "Certificate is already revoked."}), 400

    revoke_certificate(certificate, session["user_id"], reason)
    return jsonify({"message": "Certificate revoked."}), 200


@officer_bp.route("/certificates/<int:certificate_id>/download", methods=["GET"])
@role_required("officer", "admin", "citizen")
def download_certificate(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    file_path = os.path.join(current_app.config["CERT_FOLDER"], f"{certificate.certificate_number}.pdf")
    if not os.path.exists(file_path):
        return jsonify({"error": "Certificate PDF not found."}), 404
    return send_file(file_path, as_attachment=True)


@officer_bp.route("/certificates", methods=["GET"])
@role_required("officer", "admin")
def list_certificates():
    certs = Certificate.query.order_by(Certificate.created_at.desc()).limit(200).all()
    return jsonify(
        [
            {
                "id": c.id,
                "certificate_number": c.certificate_number,
                "applicant_name": c.applicant_name,
                "certificate_type": c.certificate_type.name if c.certificate_type else "-",
                "status": c.status,
                "version_number": c.version_number,
                "issue_date": c.issue_date,
                "qr_token": c.qr_token,
            }
            for c in certs
        ]
    )
