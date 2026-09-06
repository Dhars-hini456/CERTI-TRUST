"""
QR code generation for certificate verification.

The QR code only ever encodes a verification URL built around a random,
unguessable token - never personal data - so scanning the QR code cannot
leak sensitive citizen information by itself.
"""
import os
import secrets

import qrcode


def generate_qr_token() -> str:
    """Generate a unique, unguessable verification token."""
    return secrets.token_urlsafe(24)


def generate_qr_image(token: str, base_verify_url: str, qr_folder: str) -> str:
    """Create a QR code PNG encoding the verification URL for this token.

    Returns the relative static path (e.g. 'qr/<token>.png') so templates
    can reference it directly.
    """
    verify_url = f"{base_verify_url.rstrip('/')}/{token}"

    img = qrcode.make(verify_url)
    file_name = f"{token}.png"
    full_path = os.path.join(qr_folder, file_name)
    img.save(full_path)
    return f"qr/{file_name}"
