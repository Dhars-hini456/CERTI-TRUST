import uuid
from datetime import datetime

from app.extensions import db


def gen_uuid():
    return str(uuid.uuid4())


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    public_id = db.Column(db.String(36), unique=True, default=gen_uuid)
    full_name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False)  # citizen, officer, verifier, admin
    department = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)
    description = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CertificateType(db.Model):
    __tablename__ = "certificate_types"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)  # e.g. INC, CAS, BIR
    department = db.Column(db.String(120))
    validity_days = db.Column(db.Integer, default=365)
    description = db.Column(db.String(255))
    is_active = db.Column(db.Boolean, default=True)


class Application(db.Model):
    __tablename__ = "applications"

    id = db.Column(db.Integer, primary_key=True)
    application_number = db.Column(db.String(40), unique=True, nullable=False)
    citizen_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    certificate_type_id = db.Column(db.Integer, db.ForeignKey("certificate_types.id"))
    applicant_name = db.Column(db.String(150), nullable=False)
    date_of_birth = db.Column(db.String(20))
    address = db.Column(db.String(255))
    purpose = db.Column(db.String(255))
    status = db.Column(
        db.String(30), default="SUBMITTED"
    )  # SUBMITTED, UNDER_REVIEW, APPROVED, REJECTED, ISSUED
    assigned_officer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rejection_reason = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    citizen = db.relationship("User", foreign_keys=[citizen_id])
    certificate_type = db.relationship("CertificateType")


class ApplicationDocument(db.Model):
    __tablename__ = "application_documents"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=False)
    file_name = db.Column(db.String(255), nullable=False)
    stored_path = db.Column(db.String(400), nullable=False)
    document_type = db.Column(db.String(80))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Certificate(db.Model):
    __tablename__ = "certificates"

    id = db.Column(db.Integer, primary_key=True)
    certificate_number = db.Column(db.String(60), unique=True, nullable=False)
    certificate_type_id = db.Column(db.Integer, db.ForeignKey("certificate_types.id"))
    application_id = db.Column(db.Integer, db.ForeignKey("applications.id"), nullable=True)
    department = db.Column(db.String(120))
    applicant_name = db.Column(db.String(150), nullable=False)
    applicant_id = db.Column(db.String(60))
    date_of_birth = db.Column(db.String(20))
    address = db.Column(db.String(255))
    issue_date = db.Column(db.String(20))
    expiry_date = db.Column(db.String(20))
    issued_by = db.Column(db.String(150))
    officer_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    status = db.Column(db.String(30), default="ACTIVE")
    # ACTIVE, REVOKED, EXPIRED, SUPERSEDED
    version_number = db.Column(db.Integer, default=1)
    original_certificate_id = db.Column(db.Integer, db.ForeignKey("certificates.id"), nullable=True)
    reissue_reason = db.Column(db.String(255), nullable=True)
    document_hash = db.Column(db.String(128), nullable=False)
    digital_signature = db.Column(db.Text, nullable=False)
    qr_token = db.Column(db.String(64), unique=True, nullable=False)
    is_demo_data = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    certificate_type = db.relationship("CertificateType")
    versions = db.relationship(
        "Certificate", backref=db.backref("original_certificate", remote_side=[id])
    )


class CertificateVersion(db.Model):
    __tablename__ = "certificate_versions"

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey("certificates.id"), nullable=False)
    original_certificate_id = db.Column(db.Integer, db.ForeignKey("certificates.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    reissue_reason = db.Column(db.String(255))
    previous_certificate_hash = db.Column(db.String(128))
    new_certificate_hash = db.Column(db.String(128))
    reissued_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    reissued_date = db.Column(db.DateTime, default=datetime.utcnow)


class VerificationLog(db.Model):
    __tablename__ = "verification_logs"

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey("certificates.id"), nullable=True)
    verifier_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    verification_method = db.Column(db.String(30))  # QR_SCAN, CERTIFICATE_NUMBER, TOKEN, DOCUMENT_UPLOAD
    verification_result = db.Column(db.String(40))
    ip_address = db.Column(db.String(60))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    certificate = db.relationship("Certificate")
    verifier = db.relationship("User")


class FraudAlert(db.Model):
    __tablename__ = "fraud_alerts"

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.Integer, db.ForeignKey("certificates.id"), nullable=True)
    alert_type = db.Column(db.String(60), nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # LOW, MEDIUM, HIGH, CRITICAL
    reason = db.Column(db.String(255))
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    resolved = db.Column(db.Boolean, default=False)
    resolved_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    message = db.Column(db.String(400))
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    action = db.Column(db.String(150), nullable=False)
    details = db.Column(db.String(400))
    ip_address = db.Column(db.String(60))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
