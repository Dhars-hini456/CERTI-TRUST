"""
CertiTrust demo data seeder.

Run with:
    python scripts/seed_data.py

This populates departments, certificate types, demo accounts (admin,
officer, verifier, citizen), ~20 citizens, ~20 certificates (mixing
originals, official reissues, expired, revoked and a few tampered
simulation records), application records, verification logs and a
handful of fraud alerts.

All data is entirely fictional and created only for local demonstration.
"""
import os
import random
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from werkzeug.security import generate_password_hash

from app import create_app
from app.extensions import db
from app.models import (
    User, Department, CertificateType, Application, Certificate,
    VerificationLog, FraudAlert, Notification,
)
from app.services.certificate_service import issue_certificate, reissue_certificate, revoke_certificate
from app.utils.hashing import build_certificate_hash

DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "Demo@1234")

FIRST_NAMES = [
    "Ananya", "Rahul", "Priya", "Arjun", "Kavya", "Vikram", "Meera", "Rohan",
    "Divya", "Karthik", "Sneha", "Aditya", "Pooja", "Suresh", "Lakshmi",
    "Naveen", "Anjali", "Ramesh", "Deepa", "Sanjay", "Nithya", "Manoj",
]
LAST_NAMES = [
    "Sharma", "Iyer", "Reddy", "Nair", "Menon", "Rao", "Pillai", "Gupta",
    "Krishnan", "Subramaniam", "Varma", "Chandran",
]
CITIES = [
    "Chennai", "Madurai", "Coimbatore", "Trichy", "Salem", "Vellore",
    "Tirunelveli", "Erode",
]


def random_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"


def random_address():
    return f"{random.randint(1, 200)} Anna Nagar, {random.choice(CITIES)}, Tamil Nadu"


def seed():
    app = create_app()
    with app.app_context():
        print("Resetting database...")
        db.drop_all()
        db.create_all()

        print("Seeding departments...")
        departments = [
            Department(name="Revenue Department", code="REV", description="Income, caste and nativity certificates"),
            Department(name="Registrar of Births & Deaths", code="RBD", description="Birth and death certificates"),
            Department(name="Social Welfare Department", code="SWD", description="Disability and legal heir certificates"),
            Department(name="General Administration Department", code="GAD", description="Residence and misc certificates"),
        ]
        db.session.add_all(departments)
        db.session.commit()

        print("Seeding certificate types...")
        cert_types = [
            CertificateType(name="Caste / Community Certificate", code="CAS", department="Revenue Department", validity_days=1825, description="Certifies community for reservation benefits"),
            CertificateType(name="Income Certificate", code="INC", department="Revenue Department", validity_days=365, description="Certifies annual family income"),
            CertificateType(name="Nativity Certificate", code="NAT", department="Revenue Department", validity_days=3650, description="Certifies native residency status"),
            CertificateType(name="Residence Certificate", code="RES", department="General Administration Department", validity_days=1825, description="Certifies current residential address"),
            CertificateType(name="Birth Certificate", code="BIR", department="Registrar of Births & Deaths", validity_days=36500, description="Certifies date and place of birth"),
            CertificateType(name="Death Certificate", code="DEA", department="Registrar of Births & Deaths", validity_days=36500, description="Certifies date and cause of death"),
            CertificateType(name="Legal Heir Certificate", code="LEG", department="Social Welfare Department", validity_days=3650, description="Certifies legal heirs of a deceased person"),
            CertificateType(name="Disability Certificate", code="DIS", department="Social Welfare Department", validity_days=1825, description="Certifies percentage and type of disability"),
        ]
        db.session.add_all(cert_types)
        db.session.commit()

        print("Seeding demo accounts...")
        admin = User(full_name="System Administrator", email="admin@demo.local",
                     password_hash=generate_password_hash(DEMO_PASSWORD), role="admin", department="Administration")
        officer_main = User(full_name="Officer Kavitha Ramesh", email="officer@demo.local",
                             password_hash=generate_password_hash(DEMO_PASSWORD), role="officer", department="Revenue Department")
        verifier_main = User(full_name="Verifier - City College", email="verifier@demo.local",
                              password_hash=generate_password_hash(DEMO_PASSWORD), role="verifier", department="City College Admissions")
        citizen_main = User(full_name="Demo Citizen", email="citizen@demo.local",
                             password_hash=generate_password_hash(DEMO_PASSWORD), role="citizen")
        db.session.add_all([admin, officer_main, verifier_main, citizen_main])
        db.session.commit()

        print("Seeding additional officers...")
        officers = [officer_main]
        officer_depts = ["Revenue Department", "Registrar of Births & Deaths", "Social Welfare Department", "General Administration Department"]
        for i in range(4):
            officer = User(
                full_name=f"Officer {random_name()}",
                email=f"officer{i+2}@demo.local",
                password_hash=generate_password_hash(DEMO_PASSWORD),
                role="officer",
                department=officer_depts[i],
            )
            db.session.add(officer)
            officers.append(officer)
        db.session.commit()

        print("Seeding 20 citizens...")
        citizens = [citizen_main]
        for i in range(19):
            citizen = User(
                full_name=random_name(),
                email=f"citizen{i+2}@demo.local",
                password_hash=generate_password_hash(DEMO_PASSWORD),
                role="citizen",
                phone=f"98{random.randint(10000000, 99999999)}",
            )
            db.session.add(citizen)
            citizens.append(citizen)
        db.session.commit()

        print("Seeding applications and certificates...")
        active_certs = []
        for i in range(20):
            citizen = random.choice(citizens)
            cert_type = random.choice(cert_types)
            officer = random.choice(officers)
            applicant_name = citizen.full_name
            dob = (datetime(1980, 1, 1) + timedelta(days=random.randint(0, 15000))).strftime("%d-%m-%Y")
            address = random_address()

            app_number = f"APP-{100000 + i}"
            application = Application(
                application_number=app_number,
                citizen_id=citizen.id,
                certificate_type_id=cert_type.id,
                applicant_name=applicant_name,
                date_of_birth=dob,
                address=address,
                purpose="General purpose demonstration application",
                status="ISSUED",
                assigned_officer_id=officer.id,
            )
            db.session.add(application)
            db.session.commit()

            certificate = issue_certificate(
                certificate_type=cert_type,
                applicant_name=applicant_name,
                applicant_id=f"CIT-{citizen.id:05d}",
                date_of_birth=dob,
                address=address,
                issued_by=cert_type.department,
                officer_id=officer.id,
                department=cert_type.department,
                application_id=application.id,
                is_demo_data=True,
            )
            active_certs.append(certificate)

        db.session.commit()
        print(f"  Issued {len(active_certs)} original certificates.")

        # --- Official reissues (2 certificates get reissued) ---
        print("Creating official reissues...")
        reissue_targets = random.sample(active_certs, 3)
        for cert in reissue_targets:
            reissue_certificate(cert, "Original certificate copy lost by applicant", cert.officer_id)
        print(f"  Created {len(reissue_targets)} official reissues.")

        # --- Revoked certificates ---
        print("Revoking a few certificates...")
        remaining = [c for c in active_certs if c not in reissue_targets]
        revoke_targets = random.sample(remaining, 2)
        for cert in revoke_targets:
            revoke_certificate(cert, cert.officer_id, "Supporting documents found to be invalid upon audit")
        print(f"  Revoked {len(revoke_targets)} certificates.")

        # --- Expired certificates (backdate issue/expiry) ---
        print("Expiring a few certificates...")
        remaining = [c for c in remaining if c not in revoke_targets]
        expire_targets = random.sample(remaining, 2)
        for cert in expire_targets:
            cert.issue_date = (datetime.utcnow() - timedelta(days=800)).strftime("%d-%m-%Y")
            cert.expiry_date = (datetime.utcnow() - timedelta(days=30)).strftime("%d-%m-%Y")
            # Recompute hash/signature so the certificate stays internally
            # consistent (only the dates changed for demo purposes, not a tamper).
            new_hash = build_certificate_hash(
                cert.certificate_number,
                cert.certificate_type.name,
                cert.applicant_name,
                cert.applicant_id,
                cert.issue_date,
                cert.issued_by,
            )
            from app.utils.signature import sign_hash
            cert.document_hash = new_hash
            cert.digital_signature = sign_hash(new_hash)
            db.session.add(cert)
        db.session.commit()
        print(f"  Marked {len(expire_targets)} certificates as expired (via backdating).")

        # --- Tampered simulation records ---
        print("Simulating tampered certificates for the fraud demo...")
        remaining = [c for c in remaining if c not in expire_targets]
        tamper_targets = random.sample(remaining, min(3, len(remaining)))
        for cert in tamper_targets:
            # Mutate a stored field WITHOUT recomputing the hash/signature -
            # this simulates someone editing a certificate after issuance.
            cert.applicant_name = cert.applicant_name.upper() + " (MODIFIED)"
            db.session.add(cert)
        db.session.commit()
        print(f"  Simulated {len(tamper_targets)} tampered certificates.")

        # --- Verification logs & fraud alerts ---
        print("Seeding verification logs...")
        methods = ["QR_SCAN", "CERTIFICATE_NUMBER", "TOKEN"]
        results = ["VERIFIED_ORIGINAL", "VERIFIED_OFFICIAL_REISSUE", "TAMPERED_MODIFIED", "NOT_FOUND", "EXPIRED", "REVOKED"]
        for i in range(10):
            cert_choice = random.choice(active_certs) if random.random() > 0.15 else None
            log = VerificationLog(
                certificate_id=cert_choice.id if cert_choice else None,
                verifier_id=verifier_main.id,
                verification_method=random.choice(methods),
                verification_result=random.choice(results),
                ip_address=f"192.168.1.{random.randint(2, 250)}",
                user_agent="Mozilla/5.0 (Demo Seed Script)",
            )
            db.session.add(log)
        db.session.commit()

        print("Seeding fraud alerts...")
        alert_types = ["HASH_MISMATCH", "SIGNATURE_INVALID", "CERTIFICATE_NOT_FOUND", "REUSED_CERTIFICATE_NUMBER", "INVALID_ISSUE_OFFICER"]
        severities = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]
        for i in range(5):
            cert_choice = random.choice(tamper_targets) if tamper_targets and random.random() > 0.4 else None
            alert = FraudAlert(
                certificate_id=cert_choice.id if cert_choice else None,
                alert_type=random.choice(alert_types),
                severity=random.choice(severities),
                reason="Automatically flagged during demo data seeding for hackathon presentation purposes.",
                resolved=random.random() > 0.6,
            )
            db.session.add(alert)
        db.session.commit()

        print("\nSeed complete!\n")
        print("Demo accounts (password for all: {}):".format(DEMO_PASSWORD))
        print("  Admin:    admin@demo.local")
        print("  Officer:  officer@demo.local")
        print("  Verifier: verifier@demo.local")
        print("  Citizen:  citizen@demo.local")
        print("\nSample certificate numbers to try in the public verification page:")
        for c in active_certs[:3]:
            print(f"  {c.certificate_number}  -> should show VERIFIED - ORIGINAL")
        for c in reissue_targets:
            print(f"  {c.certificate_number}  -> should show VERIFIED - OFFICIAL REISSUE")
        for c in tamper_targets:
            print(f"  {c.certificate_number}  -> should show TAMPERED / MODIFIED")
        for c in revoke_targets:
            print(f"  {c.certificate_number}  -> should show REVOKED")
        for c in expire_targets:
            print(f"  {c.certificate_number}  -> should show EXPIRED")


if __name__ == "__main__":
    seed()
