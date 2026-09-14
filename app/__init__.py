"""
CertiTrust - Flask application factory.

Run with:
    python run.py

The Flask development server will start on http://localhost:5000
"""
import os
import re

from dotenv import load_dotenv

from flask import Flask, render_template

from app.extensions import db

# Load environment variables from .env if present
load_dotenv()


def normalize_database_url(url):
    """Make Render's internal ``postgres://`` URL acceptable to SQLAlchemy.

    Render exposes the managed-database connection string as
    ``postgres://user:pass@host:port/db`` (no driver). SQLAlchemy requires a
    dialect, so translate it to the psycopg 3 dialect. Plain PostgreSQL URLs
    without an explicit driver are handled the same way.
    """
    if not url:
        return url
    if url.startswith("postgres://") or url.startswith("postgresql://"):
        return re.sub(r"^postgres(ql)?://", "postgresql+psycopg://", url)
    return url


def create_app(test_config=None):
    """Create and configure the Flask application instance."""
    app = Flask(__name__)

    base_verify_url = os.getenv("BASE_VERIFY_URL")
    if not base_verify_url:
        render_url = os.getenv("RENDER_EXTERNAL_URL")
        base_verify_url = f"{render_url.rstrip('/')}/verify" if render_url else "http://localhost:5000/verify"

    # ---- Default configuration ---------------------------------------------
    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "change-this-dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=normalize_database_url(
            os.getenv("DATABASE_URL", "sqlite:///certitrust.db")
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        BASE_VERIFY_URL=base_verify_url,
        UPLOAD_FOLDER=os.path.abspath(
            os.path.join(app.root_path, "..", "uploads")
        ),
        CERT_FOLDER=os.path.abspath(
            os.path.join(app.root_path, "..", "generated_certificates")
        ),
        QR_FOLDER=os.path.abspath(
            os.path.join(app.root_path, "static", "qr")
        ),
        ALLOWED_UPLOAD_EXTENSIONS={"pdf", "png", "jpg", "jpeg"},
        MAX_CONTENT_LENGTH=16 * 1024 * 1024,  # 16 MB
        WTF_CSRF_ENABLED=False,
    )

    # Override with any test / external configuration
    if test_config:
        app.config.update(test_config)

    # ---- Ensure required folders exist --------------------------------------
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    os.makedirs(app.config["CERT_FOLDER"], exist_ok=True)
    os.makedirs(app.config["QR_FOLDER"], exist_ok=True)

    # ---- Database ------------------------------------------------------------
    db.init_app(app)

    # ---- Blueprints -----------------------------------------------------------
    from app.routes.pages import pages_bp
    from app.routes.auth import auth_bp
    from app.routes.citizen import citizen_bp
    from app.routes.officer import officer_bp
    from app.routes.verifier import verifier_bp
    from app.routes.admin import admin_bp
    from app.routes.api import api_bp
    from app.routes.verify import verify_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(citizen_bp, url_prefix="/api/citizen")
    app.register_blueprint(officer_bp, url_prefix="/api/officer")
    app.register_blueprint(verifier_bp, url_prefix="/api/verifier")
    app.register_blueprint(admin_bp, url_prefix="/api/admin")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(verify_bp)

    # ---- Error handlers ---------------------------------------------------------
    @app.errorhandler(404)
    def not_found(error):
        return render_template("errors/404.html"), 404

    # ---- Create tables and initial data on first run -----------------------------
    with app.app_context():
        db.create_all()
        if not app.config.get("TESTING"):
            _init_defaults()

    return app


def _init_defaults():
    """Seed essential departments, certificate types, and demo accounts if empty."""
    from werkzeug.security import generate_password_hash
    from app.models import Department, CertificateType, User

    demo_password = os.getenv("DEMO_PASSWORD", "Demo@1234")

    if Department.query.first() is None:
        departments = [
            Department(name="Revenue Department", code="REV", description="Income, caste and nativity certificates"),
            Department(name="Registrar of Births & Deaths", code="RBD", description="Birth and death certificates"),
            Department(name="Social Welfare Department", code="SWD", description="Disability and legal heir certificates"),
            Department(name="General Administration Department", code="GAD", description="Residence and misc certificates"),
        ]
        db.session.add_all(departments)
        db.session.commit()

    if CertificateType.query.first() is None:
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

    if User.query.first() is None:
        demo_users = [
            User(full_name="System Administrator", email="admin@demo.local", password_hash=generate_password_hash(demo_password), role="admin", department="Administration"),
            User(full_name="Officer Kavitha Ramesh", email="officer@demo.local", password_hash=generate_password_hash(demo_password), role="officer", department="Revenue Department"),
            User(full_name="Verifier - City College", email="verifier@demo.local", password_hash=generate_password_hash(demo_password), role="verifier", department="City College Admissions"),
            User(full_name="Demo Citizen", email="citizen@demo.local", password_hash=generate_password_hash(demo_password), role="citizen"),
        ]
        db.session.add_all(demo_users)
        db.session.commit()