"""
Hash-based tamper detection utility.

Important certificate fields are concatenated in a fixed, controlled order
and hashed using SHA-256. Re-computing this hash at verification time and
comparing it with the stored hash reveals whether the underlying data has
been modified after issuance.
"""
import hashlib


def build_certificate_hash(
    certificate_number: str,
    certificate_type: str,
    applicant_name: str,
    applicant_id: str,
    issue_date: str,
    issued_by: str,
) -> str:
    """Return a SHA-256 hex digest for the given certificate fields.

    The field order below is fixed on purpose: both issuance and
    verification MUST use this exact same order and format, otherwise
    every certificate would appear tampered.
    """
    payload = "|".join(
        [
            (certificate_number or "").strip(),
            (certificate_type or "").strip(),
            (applicant_name or "").strip().upper(),
            (applicant_id or "").strip(),
            (issue_date or "").strip(),
            (issued_by or "").strip(),
        ]
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def hashes_match(hash_a: str, hash_b: str) -> bool:
    """Constant-time-ish comparison wrapper (simple equality is enough here,
    but kept as a separate function so the comparison logic lives in one
    place and can be hardened later)."""
    if not hash_a or not hash_b:
        return False
    return hash_a == hash_b
