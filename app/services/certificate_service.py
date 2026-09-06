"""
Central certificate lifecycle logic: issuance, official reissue and
revocation. Kept separate from the route handlers so the same logic can be
reused from officer routes, the REST API, and the seed script.
"""
import random
from datetime import datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models import Certificate, CertificateVersion, Notification
from app.utils.hashing import build_certificate_hash
from app.utils.signature import sign_hash
from app.utils.qr_util import generate_qr_token, generate_qr_image


def _generate_certificate_number(cert_type_code: str) -> str:
    year = datetime.utcnow().year
    suffix = random.randint(100000, 999999)
    return f"{cert_type_code}-{year}-{suffix}"


def issue_certificate(
    certificate_type,
    applicant_name,
    applicant_id,
    date_of_birth,
    address,
    issued_by,
    officer_id,
    department=None,
    application_id=None,
    is_demo_data=True,
):
    """Issue a brand-new (version 1) certificate and return the ORM object."""
    issue_date = datetime.utcnow().strftime("%d-%m-%Y")
    expiry_dt = datetime.utcnow() + timedelta(days=certificate_type.validity_days or 365)
    expiry_date = expiry_dt.strftime("%d-%m-%Y")

    certificate_number = _generate_certificate_number(certificate_type.code)
    while Certificate.query.filter_by(certificate_number=certificate_number).first():
        certificate_number = _generate_certificate_number(certificate_type.code)

    doc_hash = build_certificate_hash(
        certificate_number, certificate_type.name, applicant_name, applicant_id,
        issue_date, issued_by,
    )
    signature = sign_hash(doc_hash)
    token = generate_qr_token()

    certificate = Certificate(
        certificate_number=certificate_number,
        certificate_type_id=certificate_type.id,
        application_id=application_id,
        department=department or certificate_type.department,
        applicant_name=applicant_name,
        applicant_id=applicant_id,
        date_of_birth=date_of_birth,
        address=address,
        issue_date=issue_date,
        expiry_date=expiry_date,
        issued_by=issued_by,
        officer_id=officer_id,
        status="ACTIVE",
        version_number=1,
        document_hash=doc_hash,
        digital_signature=signature,
        qr_token=token,
        is_demo_data=is_demo_data,
    )
    db.session.add(certificate)
    db.session.commit()

    generate_qr_image(
        token,
        current_app.config["BASE_VERIFY_URL"],
        current_app.config["QR_FOLDER"],
    )

    return certificate


def reissue_certificate(original_certificate: Certificate, reissue_reason: str, reissued_by_id: int):
    """Create an official duplicate/reissue of an existing certificate.

    This is NOT treated as fraud - it is explicitly tracked as an official
    reissue, versioned against the original certificate.
    """
    new_version = (
        db.session.query(db.func.max(Certificate.version_number))
        .filter(
            (Certificate.id == original_certificate.id)
            | (Certificate.original_certificate_id == original_certificate.id)
        )
        .scalar()
        or original_certificate.version_number
    )
    new_version_number = new_version + 1

    issue_date = datetime.utcnow().strftime("%d-%m-%Y")
    certificate_type = original_certificate.certificate_type

    certificate_number = _generate_certificate_number(certificate_type.code)
    while Certificate.query.filter_by(certificate_number=certificate_number).first():
        certificate_number = _generate_certificate_number(certificate_type.code)

    doc_hash = build_certificate_hash(
        certificate_number, certificate_type.name, original_certificate.applicant_name,
        original_certificate.applicant_id, issue_date, original_certificate.issued_by,
    )
    signature = sign_hash(doc_hash)
    token = generate_qr_token()

    root_id = original_certificate.original_certificate_id or original_certificate.id

    new_cert = Certificate(
        certificate_number=certificate_number,
        certificate_type_id=certificate_type.id,
        department=original_certificate.department,
        applicant_name=original_certificate.applicant_name,
        applicant_id=original_certificate.applicant_id,
        date_of_birth=original_certificate.date_of_birth,
        address=original_certificate.address,
        issue_date=issue_date,
        expiry_date=original_certificate.expiry_date,
        issued_by=original_certificate.issued_by,
        officer_id=reissued_by_id,
        status="ACTIVE",
        version_number=new_version_number,
        original_certificate_id=root_id,
        reissue_reason=reissue_reason,
        document_hash=doc_hash,
        digital_signature=signature,
        qr_token=token,
        is_demo_data=original_certificate.is_demo_data,
    )
    db.session.add(new_cert)

    # Mark the previous active version as superseded (kept in history, not fake).
    original_certificate.status = "SUPERSEDED"
    db.session.add(original_certificate)
    db.session.commit()  # new_cert.id is now populated

    version_record = CertificateVersion(
        certificate_id=new_cert.id,
        original_certificate_id=root_id,
        version_number=new_version_number,
        reissue_reason=reissue_reason,
        previous_certificate_hash=original_certificate.document_hash,
        new_certificate_hash=doc_hash,
        reissued_by=reissued_by_id,
    )
    db.session.add(version_record)
    db.session.commit()

    generate_qr_image(
        token,
        current_app.config["BASE_VERIFY_URL"],
        current_app.config["QR_FOLDER"],
    )

    return new_cert


def revoke_certificate(certificate: Certificate, revoked_by_id: int, reason: str):
    certificate.status = "REVOKED"
    db.session.add(certificate)
    db.session.commit()

    notif = Notification(
        user_id=certificate.officer_id,
        title="Certificate Revoked",
        message=f"Certificate {certificate.certificate_number} was revoked. Reason: {reason}",
    )
    db.session.add(notif)
    db.session.commit()
    return certificate


def check_and_expire(certificate: Certificate):
    """Mark a certificate as EXPIRED if past its expiry date. Non-destructive:
    only touches status, never the stored hash/signature."""
    if not certificate.expiry_date or certificate.status in ("REVOKED", "SUPERSEDED"):
        return certificate
    try:
        expiry_dt = datetime.strptime(certificate.expiry_date, "%d-%m-%Y")
    except ValueError:
        return certificate
    if expiry_dt < datetime.utcnow() and certificate.status == "ACTIVE":
        certificate.status = "EXPIRED"
        db.session.add(certificate)
        db.session.commit()
    return certificate
