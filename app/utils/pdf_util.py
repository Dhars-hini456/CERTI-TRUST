"""
Certificate PDF generation using ReportLab.
"""
import os

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas


def generate_certificate_pdf(certificate, qr_absolute_path: str, cert_folder: str) -> str:
    """Render a professional-looking certificate PDF and return its path."""
    file_name = f"{certificate.certificate_number}.pdf"
    output_path = os.path.join(cert_folder, file_name)

    c = canvas.Canvas(output_path, pagesize=A4)
    width, height = A4

    # Border
    c.setStrokeColor(colors.HexColor("#0b3d91"))
    c.setLineWidth(3)
    c.rect(15 * mm, 15 * mm, width - 30 * mm, height - 30 * mm)

    # Demo watermark banner
    c.setFillColor(colors.HexColor("#d9534f"))
    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width / 2, height - 22 * mm, "DEMO DATA - HACKATHON DEMONSTRATION ONLY")

    # Header
    c.setFillColor(colors.HexColor("#0b3d91"))
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(width / 2, height - 35 * mm, "GOVERNMENT OF DEMO STATE")
    c.setFont("Helvetica", 12)
    c.drawCentredString(width / 2, height - 42 * mm, certificate.department or "Revenue Department")

    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2, height - 55 * mm, certificate.certificate_type.name if certificate.certificate_type else "Certificate")

    # Body fields
    c.setFont("Helvetica", 11)
    y = height - 75 * mm
    line_gap = 8 * mm

    fields = [
        ("Certificate Number", certificate.certificate_number),
        ("Applicant Name", certificate.applicant_name),
        ("Applicant ID", certificate.applicant_id or "-"),
        ("Date of Birth", certificate.date_of_birth or "-"),
        ("Address", certificate.address or "-"),
        ("Issue Date", certificate.issue_date),
        ("Expiry Date", certificate.expiry_date or "Not Applicable"),
        ("Issued By", certificate.issued_by),
        ("Status", certificate.status),
        ("Version", str(certificate.version_number)),
    ]

    for label, value in fields:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(25 * mm, y, f"{label}:")
        c.setFont("Helvetica", 11)
        c.drawString(75 * mm, y, str(value))
        y -= line_gap

    # Digital signature block
    c.setFont("Helvetica-Bold", 10)
    c.drawString(25 * mm, y - 2 * mm, "Digital Signature (SHA-256 + RSA-PSS, dev keys):")
    c.setFont("Helvetica", 7)
    sig_short = (certificate.digital_signature or "")[:80] + "..."
    c.drawString(25 * mm, y - 8 * mm, sig_short)

    # QR code
    if qr_absolute_path and os.path.exists(qr_absolute_path):
        c.drawImage(
            qr_absolute_path,
            width - 60 * mm,
            25 * mm,
            width=35 * mm,
            height=35 * mm,
        )
        c.setFont("Helvetica", 8)
        c.drawCentredString(width - 42.5 * mm, 22 * mm, "Scan to verify")

    c.setFont("Helvetica-Oblique", 9)
    c.drawString(25 * mm, 30 * mm, "Verify this certificate online at the CertiTrust public verification page.")
    c.drawString(25 * mm, 25 * mm, f"Secure Certificate Identifier: {certificate.qr_token[:24]}...")

    c.showPage()
    c.save()
    return output_path
