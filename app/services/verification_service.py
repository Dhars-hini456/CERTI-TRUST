"""
Verification engine.

Implements the verification flow described in the project spec:

  scan/lookup -> find record -> check existence -> check status
  -> recompute hash -> compare with stored hash -> verify signature
  -> check reissue history -> return final result
"""
from datetime import datetime

from app.extensions import db
from app.models import Certificate, VerificationLog, FraudAlert
from app.utils.hashing import build_certificate_hash, hashes_match
from app.utils.signature import verify_signature
from app.services.certificate_service import check_and_expire

RESULT_VERIFIED_ORIGINAL = "VERIFIED_ORIGINAL"
RESULT_VERIFIED_REISSUE = "VERIFIED_OFFICIAL_REISSUE"
RESULT_TAMPERED = "TAMPERED_MODIFIED"
RESULT_FORGED = "FORGED_INVALID"
RESULT_NOT_FOUND = "NOT_FOUND"
RESULT_EXPIRED = "EXPIRED"
RESULT_REVOKED = "REVOKED"
RESULT_PENDING = "PENDING_VERIFICATION"

RESULT_LABELS = {
    RESULT_VERIFIED_ORIGINAL: "VERIFIED - ORIGINAL",
    RESULT_VERIFIED_REISSUE: "VERIFIED - OFFICIAL REISSUE / DUPLICATE",
    RESULT_TAMPERED: "TAMPERED / MODIFIED",
    RESULT_FORGED: "FORGED / INVALID",
    RESULT_NOT_FOUND: "NOT FOUND",
    RESULT_EXPIRED: "EXPIRED",
    RESULT_REVOKED: "REVOKED",
    RESULT_PENDING: "PENDING VERIFICATION",
}


def _create_alert(certificate_id, alert_type, severity, reason):
    alert = FraudAlert(
        certificate_id=certificate_id,
        alert_type=alert_type,
        severity=severity,
        reason=reason,
    )
    db.session.add(alert)
    db.session.commit()


def _log_verification(certificate_id, verifier_id, method, result, ip, user_agent):
    log = VerificationLog(
        certificate_id=certificate_id,
        verifier_id=verifier_id,
        verification_method=method,
        verification_result=result,
        ip_address=ip,
        user_agent=user_agent,
    )
    db.session.add(log)
    db.session.commit()


def _find_certificate(token=None, certificate_number=None):
    if token:
        return Certificate.query.filter_by(qr_token=token).first()
    if certificate_number:
        return Certificate.query.filter_by(certificate_number=certificate_number.strip()).first()
    return None


def verify_certificate(
    token=None,
    certificate_number=None,
    method="TOKEN",
    verifier_id=None,
    ip_address=None,
    user_agent=None,
):
    """Run the full verification algorithm and return a result dict."""
    certificate = _find_certificate(token=token, certificate_number=certificate_number)

    if not certificate:
        _log_verification(None, verifier_id, method, RESULT_NOT_FOUND, ip_address, user_agent)
        if certificate_number:
            _create_alert(
                None, "CERTIFICATE_NOT_FOUND", "MEDIUM",
                f"Verification attempted for unknown certificate number: {certificate_number}",
            )
        return {
            "result": RESULT_NOT_FOUND,
            "label": RESULT_LABELS[RESULT_NOT_FOUND],
            "certificate": None,
            "hash_valid": False,
            "signature_valid": False,
            "reason": "No certificate matches this token / certificate number.",
        }

    check_and_expire(certificate)

    if certificate.status == "REVOKED":
        _log_verification(certificate.id, verifier_id, method, RESULT_REVOKED, ip_address, user_agent)
        return {
            "result": RESULT_REVOKED,
            "label": RESULT_LABELS[RESULT_REVOKED],
            "certificate": certificate,
            "hash_valid": None,
            "signature_valid": None,
            "reason": "This certificate has been revoked by the issuing department.",
        }

    if certificate.status == "EXPIRED":
        _log_verification(certificate.id, verifier_id, method, RESULT_EXPIRED, ip_address, user_agent)
        return {
            "result": RESULT_EXPIRED,
            "label": RESULT_LABELS[RESULT_EXPIRED],
            "certificate": certificate,
            "hash_valid": None,
            "signature_valid": None,
            "reason": "This certificate has passed its expiry date.",
        }

    # Recompute hash from the current stored fields and compare.
    recomputed_hash = build_certificate_hash(
        certificate.certificate_number,
        certificate.certificate_type.name if certificate.certificate_type else "",
        certificate.applicant_name,
        certificate.applicant_id,
        certificate.issue_date,
        certificate.issued_by,
    )
    hash_ok = hashes_match(recomputed_hash, certificate.document_hash)
    signature_ok = verify_signature(certificate.document_hash, certificate.digital_signature)

    if not hash_ok:
        _create_alert(
            certificate.id, "HASH_MISMATCH", "CRITICAL",
            "Recomputed certificate hash does not match the stored hash.",
        )
        _log_verification(certificate.id, verifier_id, method, RESULT_TAMPERED, ip_address, user_agent)
        return {
            "result": RESULT_TAMPERED,
            "label": RESULT_LABELS[RESULT_TAMPERED],
            "certificate": certificate,
            "hash_valid": False,
            "signature_valid": signature_ok,
            "reason": "Certificate content does not match the official record.",
        }

    if not signature_ok:
        _create_alert(
            certificate.id, "SIGNATURE_INVALID", "CRITICAL",
            "Digital signature could not be verified against the department's public key.",
        )
        _log_verification(certificate.id, verifier_id, method, RESULT_FORGED, ip_address, user_agent)
        return {
            "result": RESULT_FORGED,
            "label": RESULT_LABELS[RESULT_FORGED],
            "certificate": certificate,
            "hash_valid": True,
            "signature_valid": False,
            "reason": "Digital signature is invalid. This certificate could not be authenticated.",
        }

    if certificate.status == "SUPERSEDED":
        # An older version being shown is not automatically fraud - just outdated.
        result = RESULT_VERIFIED_REISSUE if certificate.version_number > 1 else RESULT_VERIFIED_ORIGINAL
        _log_verification(certificate.id, verifier_id, method, result, ip_address, user_agent)
        return {
            "result": result,
            "label": RESULT_LABELS[result],
            "certificate": certificate,
            "hash_valid": True,
            "signature_valid": True,
            "reason": "This is a valid but superseded version. A newer official reissue exists.",
        }

    if certificate.version_number > 1 or certificate.original_certificate_id:
        result = RESULT_VERIFIED_REISSUE
    else:
        result = RESULT_VERIFIED_ORIGINAL

    _log_verification(certificate.id, verifier_id, method, result, ip_address, user_agent)

    return {
        "result": result,
        "label": RESULT_LABELS[result],
        "certificate": certificate,
        "hash_valid": True,
        "signature_valid": True,
        "reason": "Certificate integrity and signature verified successfully.",
    }
