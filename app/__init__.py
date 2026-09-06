"""
CertiTrust - Flask application factory.

Run with:
    python run.py

The Flask development server will start on http://localhost:5000
"""
import os

from dotenv import load_dotenv

from flask import Flask, render_template

from app.extensions import db

# Load environment variables from .env if present
load_dotenv()


def create_app(test_config=None):
    """Create and configure the Flask application instance."""
    app = Flask(__name__)

    # ---- Default configuration ---------------------------------------------
    app.config.from_mapping(
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY", "change-this-dev-secret-key"),
        SQLALCHEMY_DATABASE_URI=os.getenv(
            "DATABASE_URL", "sqlite:///certitrust.db"
        ),
        SQLALCHEMY_TRACK_MODIFICATIONS=False,
        BASE_VERIFY_URL=os.getenv(
            "BASE_VERIFY_URL", "http://localhost:5000/verify"
        ),
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

    # ---- Create tables on first run ---------------------------------------------
    with app.app_context():
        db.create_all()

    return app