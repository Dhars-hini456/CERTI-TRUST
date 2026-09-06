"""
Automated tests for CertiTrust.

Run with:
    pytest -v

These tests spin up the Flask app with an isolated temporary SQLite
database and temporary QR/certificate folders, so they never touch your
real local database or generated files.
"""
import os
import shutil
import tempfile

import pytest

from app import create_app
from app.extensions import db
from app.models import User, CertificateType, Certificate
from werkzeug.security import generate_password_hash

from app.services.certificate_service import issue_certificate, reissue_certificate, revoke_certificate
from app.services.verification_service import (
    verify_certificate,
    RESULT_VERIFIED_ORIGINAL,
    RESULT_VERIFIED_REISSUE,
    RESULT_TAMPERED,
    RESULT_NOT_FOUND,
    RESULT_REVOKED,
    RESULT_EXPIRED,
)


@pytest.fixture()
def app():
    tmp_dir = tempfile.mkdtemp(prefix="certitrust_test_")
    db_path = os.path.join(tmp_dir, "test.db")

    test_config = {
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
        "UPLOAD_FOLDER": os.path.join(tmp_dir, "uploads"),
        "CERT_FOLDER": os.path.join(tmp_dir, "generated_certificates"),
        "QR_FOLDER": os.path.join(tmp_dir, "qr"),
        "WTF_CSRF_ENABLED": False,
    }

    flask_app = create_app(test_config=test_config)

    yield flask_app

    shutil.rmtree(tmp_dir, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def sample_cert_type(app):
    with app.app_context():
        ct = CertificateType(name="Income Certificate", code="INC", department="Revenue Department", validity_days=365)
        db.session.add(ct)
        db.session.commit()
        return ct.id


@pytest.fixture()
def sample_officer(app):
    with app.app_context():
        officer = User(
            full_name="Test Officer",
            email="officer@test.local",
            password_hash=generate_password_hash("Demo@1234"),
            role="officer",
            department="Revenue Department",
        )
        db.session.add(officer)
        db.session.commit()
        return officer.id


# ---------------------------------------------------------------------------
# Registration & login
# ---------------------------------------------------------------------------

def test_register_creates_citizen(client):
    resp = client.post(
        "/api/auth/register",
        json={"full_name": "Ananya Sharma", "email": "ananya@test.local", "password": "Demo@1234"},
    )
    assert resp.status_code == 201


def test_register_rejects_short_password(client):
    resp = client.post(
        "/api/auth/register",
        json={"full_name": "Ananya Sharma", "email": "ananya2@test.local", "password": "123"},
    )
    assert resp.status_code == 400


def test_register_rejects_duplicate_email(client):
    client.post("/api/auth/register", json={"full_name": "A B", "email": "dup@test.local", "password": "Demo@1234"})
    resp = client.post("/api/auth/register", json={"full_name": "C D", "email": "dup@test.local", "password": "Demo@1234"})
    assert resp.status_code == 409


def test_login_success_and_failure(client):
    client.post("/api/auth/register", json={"full_name": "Login Test", "email": "login@test.local", "password": "Demo@1234"})

    good = client.post("/api/auth/login", json={"email": "login@test.local", "password": "Demo@1234"})
    assert good.status_code == 200
    assert good.get_json()["role"] == "citizen"

    bad = client.post("/api/auth/login", json={"email": "login@test.local", "password": "wrong-password"})
    assert bad.status_code == 401


# ---------------------------------------------------------------------------
# Certificate issuance, QR generation, and verification
# ---------------------------------------------------------------------------

def test_issue_certificate_creates_valid_record(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        cert = issue_certificate(
            certificate_type=ct,
            applicant_name="Test Applicant",
            applicant_id="CIT-00001",
            date_of_birth="01-01-1995",
            address="123 Test Street",
            issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        assert cert.id is not None
        assert cert.status == "ACTIVE"
        assert cert.version_number == 1
        assert len(cert.document_hash) == 64  # SHA-256 hex digest length
        assert cert.digital_signature

        qr_path = os.path.join(app.config["QR_FOLDER"], f"{cert.qr_token}.png")
        assert os.path.exists(qr_path)


def test_valid_verification_returns_original(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        cert = issue_certificate(
            certificate_type=ct, applicant_name="Test Applicant", applicant_id="CIT-00002",
            date_of_birth="01-01-1995", address="Addr", issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        outcome = verify_certificate(certificate_number=cert.certificate_number, method="CERTIFICATE_NUMBER")
        assert outcome["result"] == RESULT_VERIFIED_ORIGINAL
        assert outcome["hash_valid"] is True
        assert outcome["signature_valid"] is True


def test_verification_of_unknown_certificate_returns_not_found(app):
    with app.app_context():
        outcome = verify_certificate(certificate_number="DOES-NOT-EXIST-0001", method="CERTIFICATE_NUMBER")
        assert outcome["result"] == RESULT_NOT_FOUND


def test_tampered_certificate_is_detected(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        cert = issue_certificate(
            certificate_type=ct, applicant_name="Original Name", applicant_id="CIT-00003",
            date_of_birth="01-01-1995", address="Addr", issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        # Simulate someone editing the certificate record after issuance
        # without regenerating the hash/signature.
        cert.applicant_name = "Modified Name"
        db.session.add(cert)
        db.session.commit()

        outcome = verify_certificate(certificate_number=cert.certificate_number, method="CERTIFICATE_NUMBER")
        assert outcome["result"] == RESULT_TAMPERED
        assert outcome["hash_valid"] is False


def test_invalid_signature_is_detected(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        cert = issue_certificate(
            certificate_type=ct, applicant_name="Sig Test", applicant_id="CIT-00004",
            date_of_birth="01-01-1995", address="Addr", issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        cert.digital_signature = "clearly-not-a-valid-signature"
        db.session.add(cert)
        db.session.commit()

        outcome = verify_certificate(certificate_number=cert.certificate_number, method="CERTIFICATE_NUMBER")
        assert outcome["result"] == "FORGED_INVALID"
        assert outcome["signature_valid"] is False


def test_reissued_certificate_is_verified_reissue_not_fake(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        original = issue_certificate(
            certificate_type=ct, applicant_name="Reissue Test", applicant_id="CIT-00005",
            date_of_birth="01-01-1995", address="Addr", issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        new_cert = reissue_certificate(original, "Lost original copy", sample_officer)

        assert new_cert.version_number == 2
        assert new_cert.original_certificate_id == original.id

        outcome = verify_certificate(certificate_number=new_cert.certificate_number, method="CERTIFICATE_NUMBER")
        assert outcome["result"] == RESULT_VERIFIED_REISSUE

        # The original certificate should now be marked superseded, not fake.
        refreshed_original = Certificate.query.get(original.id)
        assert refreshed_original.status == "SUPERSEDED"


def test_revoked_certificate_is_detected(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        cert = issue_certificate(
            certificate_type=ct, applicant_name="Revoke Test", applicant_id="CIT-00006",
            date_of_birth="01-01-1995", address="Addr", issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        revoke_certificate(cert, sample_officer, "Fraudulent documents discovered")

        outcome = verify_certificate(certificate_number=cert.certificate_number, method="CERTIFICATE_NUMBER")
        assert outcome["result"] == RESULT_REVOKED


def test_expired_certificate_is_detected(app, sample_cert_type, sample_officer):
    with app.app_context():
        ct = CertificateType.query.get(sample_cert_type)
        cert = issue_certificate(
            certificate_type=ct, applicant_name="Expiry Test", applicant_id="CIT-00007",
            date_of_birth="01-01-1995", address="Addr", issued_by="Revenue Department",
            officer_id=sample_officer,
        )
        cert.expiry_date = "01-01-2000"  # forcibly backdate to the past
        db.session.add(cert)
        db.session.commit()

        outcome = verify_certificate(certificate_number=cert.certificate_number, method="CERTIFICATE_NUMBER")
        assert outcome["result"] == RESULT_EXPIRED


# ---------------------------------------------------------------------------
# Role-based authorization
# ---------------------------------------------------------------------------

def test_citizen_cannot_access_officer_api(client):
    client.post("/api/auth/register", json={"full_name": "Plain Citizen", "email": "citizen@test.local", "password": "Demo@1234"})
    client.post("/api/auth/login", json={"email": "citizen@test.local", "password": "Demo@1234"})

    resp = client.get("/api/officer/applications")
    assert resp.status_code == 403


def test_unauthenticated_user_cannot_access_dashboard_api(client):
    resp = client.get("/api/dashboard")
    assert resp.status_code == 401


def test_public_verify_page_loads(client):
    resp = client.get("/verify")
    assert resp.status_code == 200


def test_public_stats_endpoint_requires_no_login(client):
    resp = client.get("/api/public-stats")
    assert resp.status_code == 200
    body = resp.get_json()
    assert "total_certificates" in body
    assert "total_verification_requests" in body
