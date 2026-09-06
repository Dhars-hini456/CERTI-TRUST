from flask import Blueprint, render_template, session, redirect, url_for

from app.models import CertificateType, Application, Certificate
from app.utils.decorators import login_required, role_required

pages_bp = Blueprint("pages", __name__)


@pages_bp.route("/")
def index():
    return render_template("index.html")


@pages_bp.route("/login")
def login_page():
    if "user_id" in session:
        return redirect(url_for("pages.dashboard_redirect"))
    return render_template("login.html")


@pages_bp.route("/register")
def register_page():
    if "user_id" in session:
        return redirect(url_for("pages.dashboard_redirect"))
    return render_template("register.html")


@pages_bp.route("/dashboard")
def dashboard_redirect():
    role = session.get("role")
    mapping = {
        "citizen": "pages.citizen_dashboard",
        "officer": "pages.officer_dashboard",
        "verifier": "pages.verifier_dashboard",
        "admin": "pages.admin_dashboard",
    }
    if role in mapping:
        return redirect(url_for(mapping[role]))
    return redirect(url_for("pages.login_page"))


@pages_bp.route("/citizen-dashboard")
@role_required("citizen")
def citizen_dashboard():
    cert_types = CertificateType.query.filter_by(is_active=True).all()
    return render_template("citizen_dashboard.html", cert_types=cert_types)


@pages_bp.route("/officer-dashboard")
@role_required("officer", "admin")
def officer_dashboard():
    return render_template("officer_dashboard.html")


@pages_bp.route("/verifier-dashboard")
@role_required("verifier", "admin")
def verifier_dashboard():
    return render_template("verifier_dashboard.html")


@pages_bp.route("/admin-dashboard")
@role_required("admin")
def admin_dashboard():
    return render_template("admin_dashboard.html")


@pages_bp.route("/applications")
@role_required("citizen", "officer", "admin")
def applications_page():
    return render_template("applications.html")


@pages_bp.route("/certificate/<int:certificate_id>")
@login_required
def certificate_details_page(certificate_id):
    certificate = Certificate.query.get_or_404(certificate_id)
    return render_template("certificate_details.html", certificate=certificate)


@pages_bp.route("/verification-history")
@role_required("officer", "admin", "verifier")
def verification_history_page():
    return render_template("verification_history.html")


@pages_bp.route("/alerts")
@role_required("officer", "admin")
def alerts_page():
    return render_template("alerts.html")


@pages_bp.route("/profile")
@login_required
def profile_page():
    return render_template("profile.html")
