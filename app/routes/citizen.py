import os
import random
import uuid

from flask import Blueprint, request, jsonify, session, current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Application, ApplicationDocument, CertificateType, Certificate, Notification
from app.utils.decorators import role_required

citizen_bp = Blueprint("citizen", __name__)


def _allowed_file(filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return ext in current_app.config["ALLOWED_UPLOAD_EXTENSIONS"]


@citizen_bp.route("/applications", methods=["GET"])
@role_required("citizen")
def my_applications():
    apps = (
        Application.query.filter_by(citizen_id=session["user_id"])
        .order_by(Application.created_at.desc())
        .all()
    )
    return jsonify(
        [
            {
                "id": a.id,
                "application_number": a.application_number,
                "certificate_type": a.certificate_type.name if a.certificate_type else "-",
                "status": a.status,
                "created_at": a.created_at.strftime("%d-%m-%Y %H:%M"),
                "rejection_reason": a.rejection_reason,
            }
            for a in apps
        ]
    )


@citizen_bp.route("/applications", methods=["POST"])
@role_required("citizen")
def submit_application():
    data = request.get_json(silent=True) or request.form

    cert_type_id = data.get("certificate_type_id")
    applicant_name = (data.get("applicant_name") or "").strip()
    date_of_birth = (data.get("date_of_birth") or "").strip()
    address = (data.get("address") or "").strip()
    purpose = (data.get("purpose") or "").strip()

    if not cert_type_id or not applicant_name:
        return jsonify({"error": "Certificate type and applicant name are required."}), 400

    cert_type = CertificateType.query.get(cert_type_id)
    if not cert_type or not cert_type.is_active:
        return jsonify({"error": "Invalid certificate type."}), 400

    application_number = f"APP-{random.randint(100000, 999999)}"
    while Application.query.filter_by(application_number=application_number).first():
        application_number = f"APP-{random.randint(100000, 999999)}"

    application = Application(
        application_number=application_number,
        citizen_id=session["user_id"],
        certificate_type_id=cert_type.id,
        applicant_name=applicant_name,
        date_of_birth=date_of_birth,
        address=address,
        purpose=purpose,
        status="SUBMITTED",
    )
    db.session.add(application)
    db.session.commit()

    db.session.add(
        Notification(
            user_id=session["user_id"],
            title="Application Submitted",
            message=f"Your application {application_number} has been submitted for review.",
        )
    )
    db.session.commit()

    return jsonify({"message": "Application submitted.", "application_number": application_number}), 201


@citizen_bp.route("/applications/<int:application_id>/documents", methods=["POST"])
@role_required("citizen")
def upload_document(application_id):
    application = Application.query.get_or_404(application_id)
    if application.citizen_id != session["user_id"]:
        return jsonify({"error": "Not authorized for this application."}), 403

    if "file" not in request.files:
        return jsonify({"error": "No file provided."}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No file selected."}), 400
    if not _allowed_file(file.filename):
        return jsonify({"error": "File type not allowed. Use PDF, PNG or JPG."}), 400

    safe_name = secure_filename(file.filename)
    unique_name = f"{uuid.uuid4().hex}_{safe_name}"
    dest_path = os.path.join(current_app.config["UPLOAD_FOLDER"], unique_name)
    file.save(dest_path)

    doc = ApplicationDocument(
        application_id=application.id,
        file_name=safe_name,
        stored_path=dest_path,
        document_type=request.form.get("document_type", "supporting_document"),
    )
    db.session.add(doc)
    db.session.commit()

    return jsonify({"message": "Document uploaded successfully."}), 201


@citizen_bp.route("/certificates", methods=["GET"])
@role_required("citizen")
def my_certificates():
    apps = Application.query.filter_by(citizen_id=session["user_id"]).all()
    app_ids = [a.id for a in apps]
    certs = Certificate.query.filter(Certificate.application_id.in_(app_ids)).all() if app_ids else []
    return jsonify(
        [
            {
                "id": c.id,
                "certificate_number": c.certificate_number,
                "certificate_type": c.certificate_type.name if c.certificate_type else "-",
                "status": c.status,
                "issue_date": c.issue_date,
                "expiry_date": c.expiry_date,
                "qr_token": c.qr_token,
            }
            for c in certs
        ]
    )
