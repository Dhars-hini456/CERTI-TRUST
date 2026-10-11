"""
CertiTrust Model Context Protocol (MCP) Server.

Exposes CertiTrust verification, certificate lifecycle management, fraud alert
monitoring, department configurations, and system analytics as standard MCP
tools, resources, and prompts for AI assistants (Antigravity, Claude, Cursor, etc.).
"""
import argparse
import json
import logging
import sys
from datetime import datetime
from typing import Any, Dict, List, Optional

from app import create_app
from app.extensions import db
from app.models import (
    Application,
    Certificate,
    CertificateType,
    CertificateVersion,
    Department,
    FraudAlert,
    Notification,
    User,
    VerificationLog,
)
from app.services.certificate_service import issue_certificate
from app.services.verification_service import verify_certificate
from mcp.server.mcpserver import MCPServer

# Configure logging to stderr so stdout remains clean for stdio JSON-RPC transport
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("certitrust-mcp")

# Initialize Flask app
flask_app = create_app()

# Initialize MCPServer instance
server = MCPServer("certitrust")


# ---------------------------------------------------------------------------
# Helper Serializers
# ---------------------------------------------------------------------------

def _serialize_cert(c: Certificate) -> Dict[str, Any]:
    if not c:
        return {}
    return {
        "id": c.id,
        "certificate_number": c.certificate_number,
        "applicant_name": c.applicant_name,
        "applicant_id": c.applicant_id,
        "date_of_birth": c.date_of_birth,
        "address": c.address,
        "certificate_type": c.certificate_type.name if c.certificate_type else None,
        "certificate_type_code": c.certificate_type.code if c.certificate_type else None,
        "department": c.department or (c.certificate_type.department if c.certificate_type else None),
        "status": c.status,
        "version_number": c.version_number,
        "original_certificate_id": c.original_certificate_id,
        "is_reissue": (c.version_number or 1) > 1,
        "reissue_reason": c.reissue_reason,
        "issue_date": c.issue_date,
        "expiry_date": c.expiry_date,
        "issued_by": c.issued_by,
        "qr_token": c.qr_token,
        "document_hash": c.document_hash,
        "digital_signature_present": bool(c.digital_signature),
    }


def _serialize_alert(a: FraudAlert) -> Dict[str, Any]:
    return {
        "id": a.id,
        "alert_type": a.alert_type,
        "severity": a.severity,
        "reason": a.reason,
        "certificate_id": a.certificate_id,
        "certificate_number": a.certificate.certificate_number if a.certificate else None,
        "resolved": a.resolved,
        "resolved_by": a.resolved_by,
        "resolution_notes": a.resolution_notes,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "resolved_at": a.resolved_at.isoformat() if a.resolved_at else None,
    }


def _serialize_application(app_record: Application) -> Dict[str, Any]:
    return {
        "id": app_record.id,
        "application_number": app_record.application_number,
        "applicant_name": app_record.applicant_name,
        "certificate_type": app_record.certificate_type.name if app_record.certificate_type else None,
        "department": app_record.certificate_type.department if app_record.certificate_type else None,
        "purpose": app_record.purpose,
        "status": app_record.status,
        "remarks": app_record.remarks,
        "created_at": app_record.created_at.isoformat() if app_record.created_at else None,
    }


# ---------------------------------------------------------------------------
# MCP Tools
# ---------------------------------------------------------------------------

@server.tool()
def verify_certificate_record(identifier: str) -> Dict[str, Any]:
    """Verify a government certificate by QR token or certificate number.

    Performs full cryptographic verification including:
    - Database record existence
    - Validity and active/expired/revoked status
    - SHA-256 hash recomputation across canonical fields
    - RSA-2048 digital signature verification against department public key
    - Official reissue version history check

    Args:
        identifier: Either a QR verification token or certificate number (e.g. 'INC-2026-123456').
    """
    with flask_app.app_context():
        clean_id = (identifier or "").strip()
        if not clean_id:
            return {"error": "Identifier is required"}

        # Detect whether identifier is likely a QR token (long alphanumeric) or cert number
        is_token = len(clean_id) >= 20 and "-" not in clean_id
        if is_token:
            outcome = verify_certificate(
                token=clean_id,
                method="MCP",
                user_agent="CertiTrust-MCP-Server",
            )
        else:
            outcome = verify_certificate(
                certificate_number=clean_id,
                method="MCP",
                user_agent="CertiTrust-MCP-Server",
            )

        cert = outcome.pop("certificate", None)
        outcome["certificate"] = _serialize_cert(cert) if cert else None
        outcome["is_valid"] = outcome.get("result") in ("VERIFIED_ORIGINAL", "VERIFIED_OFFICIAL_REISSUE")
        outcome["is_official_reissue"] = outcome.get("result") == "VERIFIED_OFFICIAL_REISSUE"
        outcome["is_tampered"] = outcome.get("result") == "TAMPERED_MODIFIED"
        return outcome


@server.tool()
def get_certificate_details(certificate_number: str) -> Dict[str, Any]:
    """Get complete details, history, and cryptographic signatures for a certificate.

    Args:
        certificate_number: The unique certificate number (e.g., 'INC-2026-102938').
    """
    with flask_app.app_context():
        cert = Certificate.query.filter_by(certificate_number=certificate_number.strip()).first()
        if not cert:
            return {
                "found": False,
                "message": f"Certificate '{certificate_number}' not found in registry.",
            }

        verification_count = VerificationLog.query.filter_by(certificate_id=cert.id).count()
        serialized = _serialize_cert(cert)
        serialized["found"] = True
        serialized["total_verifications"] = verification_count
        return serialized


@server.tool()
def get_certificate_version_history(certificate_number: str) -> Dict[str, Any]:
    """Retrieve the original certificate and its official reissue chain."""
    with flask_app.app_context():
        clean_number = (certificate_number or "").strip()
        if not clean_number:
            return {"found": False, "error": "Certificate number is required."}

        cert = Certificate.query.filter_by(certificate_number=clean_number).first()
        if not cert:
            return {"found": False, "message": f"Certificate '{clean_number}' not found."}

        root_id = cert.original_certificate_id or cert.id
        versions = (
            Certificate.query.filter(
                (Certificate.id == root_id)
                | (Certificate.original_certificate_id == root_id)
            )
            .order_by(Certificate.version_number.asc())
            .all()
        )
        transitions = {
            record.version_number: record
            for record in CertificateVersion.query.filter_by(
                original_certificate_id=root_id
            ).all()
        }

        return {
            "found": True,
            "root_certificate_number": versions[0].certificate_number,
            "version_count": len(versions),
            "versions": [
                {
                    "certificate_number": version.certificate_number,
                    "version_number": version.version_number,
                    "status": version.status,
                    "issue_date": version.issue_date,
                    "expiry_date": version.expiry_date,
                    "reissue_reason": version.reissue_reason,
                    "document_hash": version.document_hash,
                    "digital_signature_present": bool(version.digital_signature),
                    "reissued_at": (
                        transitions[version.version_number].reissued_date.isoformat()
                        if version.version_number in transitions
                        and transitions[version.version_number].reissued_date
                        else None
                    ),
                }
                for version in versions
            ],
        }


@server.tool()
def search_certificates(
    query: str = "",
    status: str = "",
    limit: int = 10,
) -> Dict[str, Any]:
    """Search registered certificates by applicant name, certificate number, or department.

    Args:
        query: Search string to match applicant name or certificate number.
        status: Optional status filter ('ACTIVE', 'EXPIRED', 'REVOKED').
        limit: Max results to return (default 10, max 50).
    """
    with flask_app.app_context():
        limit = max(1, min(limit, 50))
        q = Certificate.query

        if query:
            clean_q = f"%{query.strip()}%"
            q = q.filter(
                (Certificate.certificate_number.ilike(clean_q))
                | (Certificate.applicant_name.ilike(clean_q))
                | (Certificate.department.ilike(clean_q))
            )

        if status:
            q = q.filter(Certificate.status == status.strip().upper())

        certs = q.order_by(Certificate.id.desc()).limit(limit).all()
        return {
            "count": len(certs),
            "certificates": [_serialize_cert(c) for c in certs],
        }


@server.tool()
def list_certificate_types() -> List[Dict[str, Any]]:
    """List all supported government certificate types and their issuing departments."""
    with flask_app.app_context():
        types = CertificateType.query.filter_by(is_active=True).all()
        return [
            {
                "id": t.id,
                "name": t.name,
                "code": t.code,
                "department": t.department,
                "validity_days": t.validity_days,
                "description": t.description,
            }
            for t in types
        ]


@server.tool()
def list_departments() -> List[Dict[str, Any]]:
    """List all registered government departments issuing certificates."""
    with flask_app.app_context():
        depts = Department.query.order_by(Department.name.asc()).all()
        return [
            {
                "id": d.id,
                "name": d.name,
                "code": d.code,
                "description": d.description,
            }
            for d in depts
        ]


@server.tool()
def get_dashboard_analytics() -> Dict[str, Any]:
    """Get real-time CertiTrust platform metrics and security health statistics."""
    with flask_app.app_context():
        total_certs = Certificate.query.count()
        active_certs = Certificate.query.filter_by(status="ACTIVE").count()
        reissued_certs = Certificate.query.filter(Certificate.version_number > 1).count()
        revoked_certs = Certificate.query.filter_by(status="REVOKED").count()
        expired_certs = Certificate.query.filter_by(status="EXPIRED").count()
        pending_apps = Application.query.filter(
            Application.status.in_(["SUBMITTED", "UNDER_REVIEW"])
        ).count()
        total_verifications = VerificationLog.query.count()
        unresolved_fraud_alerts = FraudAlert.query.filter_by(resolved=False).count()

        return {
            "timestamp": datetime.utcnow().isoformat(),
            "total_certificates": total_certs,
            "active_certificates": active_certs,
            "official_reissues": reissued_certs,
            "revoked_certificates": revoked_certs,
            "expired_certificates": expired_certs,
            "pending_applications": pending_apps,
            "total_verifications": total_verifications,
            "unresolved_fraud_alerts": unresolved_fraud_alerts,
        }


@server.tool()
def get_department_analytics(department: str) -> Dict[str, Any]:
    """Return certificate, pending application, and unresolved alert totals for a department."""
    with flask_app.app_context():
        clean_department = (department or "").strip()
        if not clean_department:
            return {"error": "Department is required."}

        department_filter = Certificate.department.ilike(f"%{clean_department}%")
        status_rows = (
            db.session.query(Certificate.status, db.func.count(Certificate.id))
            .filter(department_filter)
            .group_by(Certificate.status)
            .all()
        )
        pending_applications = (
            Application.query.join(CertificateType)
            .filter(
                CertificateType.department.ilike(f"%{clean_department}%"),
                Application.status.in_(["SUBMITTED", "UNDER_REVIEW"]),
            )
            .count()
        )
        unresolved_alerts = (
            FraudAlert.query.join(Certificate)
            .filter(department_filter, FraudAlert.resolved.is_(False))
            .count()
        )

        return {
            "department": clean_department,
            "total_certificates": sum(count for _, count in status_rows),
            "certificates_by_status": {
                status: count for status, count in status_rows
            },
            "pending_applications": pending_applications,
            "unresolved_fraud_alerts": unresolved_alerts,
        }


@server.tool()
def list_pending_applications(
    department: str = "",
    limit: int = 10,
) -> Dict[str, Any]:
    """List citizen applications awaiting officer review or approval.

    Args:
        department: Optional department name filter.
        limit: Max applications to retrieve (default 10).
    """
    with flask_app.app_context():
        limit = max(1, min(limit, 50))
        q = Application.query.filter(
            Application.status.in_(["SUBMITTED", "UNDER_REVIEW"])
        )

        if department:
            q = q.join(CertificateType).filter(
                CertificateType.department.ilike(f"%{department.strip()}%")
            )

        apps = q.order_by(Application.created_at.asc()).limit(limit).all()
        return {
            "count": len(apps),
            "applications": [_serialize_application(a) for a in apps],
        }


@server.tool()
def review_application(
    application_number: str,
    action: str,
    remarks: str = "",
    officer_name: str = "MCP Officer",
) -> Dict[str, Any]:
    """Review a citizen application (APPROVE, REJECT, or mark UNDER_REVIEW).

    Approving will automatically issue a digitally signed, tamper-evident certificate.

    Args:
        application_number: Unique application number (e.g. 'APP-102938').
        action: One of 'APPROVE', 'REJECT', 'UNDER_REVIEW'.
        remarks: Decision explanation or comments.
        officer_name: Name of the officer processing the action.
    """
    with flask_app.app_context():
        action_upper = action.strip().upper()
        if action_upper not in ("APPROVE", "REJECT", "UNDER_REVIEW"):
            return {
                "success": False,
                "error": "Action must be 'APPROVE', 'REJECT', or 'UNDER_REVIEW'.",
            }

        app_record = Application.query.filter_by(
            application_number=application_number.strip()
        ).first()
        if not app_record:
            return {
                "success": False,
                "error": f"Application '{application_number}' not found.",
            }

        officer_user = User.query.filter_by(role="officer").first()
        officer_id = officer_user.id if officer_user else 1

        if action_upper == "APPROVE":
            app_record.status = "APPROVED"
            app_record.remarks = remarks or "Approved via MCP agent."
            app_record.officer_id = officer_id

            # Issue certificate
            cert = issue_certificate(
                certificate_type=app_record.certificate_type,
                applicant_name=app_record.applicant_name,
                applicant_id=app_record.citizen.email if app_record.citizen else "MCP-CITIZEN",
                date_of_birth=app_record.date_of_birth or "01-01-2000",
                address=app_record.address or "Registry record",
                issued_by=officer_name,
                officer_id=officer_id,
                department=app_record.certificate_type.department if app_record.certificate_type else None,
                application_id=app_record.id,
                is_demo_data=False,
            )
            db.session.commit()
            return {
                "success": True,
                "status": "APPROVED",
                "message": f"Application approved. Certificate {cert.certificate_number} issued.",
                "certificate": _serialize_cert(cert),
            }

        elif action_upper == "REJECT":
            app_record.status = "REJECTED"
            app_record.remarks = remarks or "Rejected via MCP agent."
            app_record.officer_id = officer_id
            db.session.commit()
            return {
                "success": True,
                "status": "REJECTED",
                "message": f"Application {application_number} rejected.",
            }

        else:
            app_record.status = "UNDER_REVIEW"
            app_record.remarks = remarks or "Marked under review via MCP agent."
            app_record.officer_id = officer_id
            db.session.commit()
            return {
                "success": True,
                "status": "UNDER_REVIEW",
                "message": f"Application {application_number} marked under review.",
            }


@server.tool()
def list_fraud_alerts(
    unresolved_only: bool = True,
    limit: int = 20,
) -> Dict[str, Any]:
    """List fraud detection alerts (tampering attempts, fake lookups, signature failures).

    Args:
        unresolved_only: Whether to only return unresolved alerts (default: True).
        limit: Max alerts to return (default: 20).
    """
    with flask_app.app_context():
        limit = max(1, min(limit, 100))
        q = FraudAlert.query
        if unresolved_only:
            q = q.filter_by(resolved=False)

        alerts = q.order_by(FraudAlert.created_at.desc()).limit(limit).all()
        return {
            "count": len(alerts),
            "alerts": [_serialize_alert(a) for a in alerts],
        }


@server.tool()
def resolve_fraud_alert(
    alert_id: int,
    resolution_notes: str,
    resolved_by: str = "MCP Auditor",
) -> Dict[str, Any]:
    """Mark a fraud alert as resolved with audit investigation notes.

    Args:
        alert_id: The ID of the alert to resolve.
        resolution_notes: Detailed explanation of resolution or finding.
        resolved_by: Identity of the investigator / auditor resolving the alert.
    """
    with flask_app.app_context():
        alert = FraudAlert.query.get(alert_id)
        if not alert:
            return {"success": False, "error": f"Fraud alert ID {alert_id} not found."}

        alert.resolved = True
        alert.resolved_by = resolved_by
        alert.resolved_at = datetime.utcnow()
        alert.resolution_notes = resolution_notes.strip()
        db.session.commit()

        return {
            "success": True,
            "message": f"Alert {alert_id} resolved successfully.",
            "alert": _serialize_alert(alert),
        }


@server.tool()
def get_verification_audit_trail(
    certificate_number: str = "",
    limit: int = 20,
) -> Dict[str, Any]:
    """Retrieve the verification audit log history.

    Args:
        certificate_number: Optional certificate number to filter logs for.
        limit: Max records to return (default: 20).
    """
    with flask_app.app_context():
        limit = max(1, min(limit, 100))
        q = VerificationLog.query

        if certificate_number:
            cert = Certificate.query.filter_by(
                certificate_number=certificate_number.strip()
            ).first()
            if not cert:
                return {
                    "count": 0,
                    "logs": [],
                    "message": f"Certificate '{certificate_number}' not found.",
                }
            q = q.filter_by(certificate_id=cert.id)

        logs = q.order_by(VerificationLog.timestamp.desc()).limit(limit).all()
        return {
            "count": len(logs),
            "logs": [
                {
                    "id": l.id,
                    "certificate_number": l.certificate.certificate_number if l.certificate else None,
                    "verification_method": l.verification_method,
                    "verification_result": l.verification_result,
                    "ip_address": l.ip_address,
                    "user_agent": l.user_agent,
                    "verified_at": l.timestamp.isoformat() if l.timestamp else None,
                }
                for l in logs
            ],
        }


@server.tool()
def list_recent_verifications(
    result_filter: str = "",
    limit: int = 20,
) -> Dict[str, Any]:
    """List recent verification events without exposing IP addresses or user agents."""
    with flask_app.app_context():
        limit = max(1, min(limit, 100))
        query = VerificationLog.query
        clean_result = (result_filter or "").strip()
        if clean_result:
            query = query.filter(
                VerificationLog.verification_result.ilike(f"%{clean_result}%")
            )

        logs = query.order_by(VerificationLog.timestamp.desc()).limit(limit).all()
        return {
            "count": len(logs),
            "verifications": [
                {
                    "certificate_number": (
                        log.certificate.certificate_number if log.certificate else None
                    ),
                    "verification_method": log.verification_method,
                    "verification_result": log.verification_result,
                    "verified_at": log.timestamp.isoformat() if log.timestamp else None,
                }
                for log in logs
            ],
        }


@server.tool()
def revoke_certificate_record(
    certificate_number: str,
    reason: str,
    revoked_by: str = "MCP Officer",
) -> Dict[str, Any]:
    """Revoke an active certificate due to fraud, error, or court order.

    Args:
        certificate_number: The certificate number to revoke.
        reason: Justification for revocation.
        revoked_by: Name or identity of the revoking official.
    """
    with flask_app.app_context():
        cert = Certificate.query.filter_by(certificate_number=certificate_number.strip()).first()
        if not cert:
            return {"success": False, "error": f"Certificate '{certificate_number}' not found."}

        cert.status = "REVOKED"

        # Create security alert for revocation
        alert = FraudAlert(
            certificate_id=cert.id,
            alert_type="CERTIFICATE_REVOKED",
            severity="HIGH",
            reason=f"Certificate revoked by {revoked_by}. Reason: {reason}",
            resolved=True,
            resolved_by=revoked_by,
            resolved_at=datetime.utcnow(),
            resolution_notes=f"Revocation executed: {reason}",
        )
        db.session.add(alert)
        db.session.commit()

        return {
            "success": True,
            "message": f"Certificate {certificate_number} has been revoked.",
            "certificate": _serialize_cert(cert),
        }


# ---------------------------------------------------------------------------
# MCP Resources
# ---------------------------------------------------------------------------

@server.resource("certitrust://stats")
def resource_stats() -> str:
    """Current aggregate system statistics in JSON format."""
    stats = get_dashboard_analytics()
    return json.dumps(stats, indent=2)


@server.resource("certitrust://certificate-types")
def resource_types() -> str:
    """List of all registered certificate types in JSON format."""
    types = list_certificate_types()
    return json.dumps(types, indent=2)


@server.resource("certitrust://unresolved-alerts")
def resource_alerts() -> str:
    """List of active unresolved fraud alerts in JSON format."""
    alerts = list_fraud_alerts(unresolved_only=True)
    return json.dumps(alerts, indent=2)


# ---------------------------------------------------------------------------
# MCP Prompts
# ---------------------------------------------------------------------------

@server.prompt()
def audit_certificate(certificate_number: str) -> str:
    """Prompt template for auditing a certificate's integrity and reissue history."""
    return (
        f"You are a forensic document auditor evaluating certificate {certificate_number}.\n"
        f"Use the `verify_certificate_record` and `get_certificate_details` tools to inspect:\n"
        f"1. Whether the digital signature matches the department RSA public key.\n"
        f"2. Whether the SHA-256 document hash matches the canonical fields.\n"
        f"3. Whether this certificate is an official reissue or original version.\n"
        f"4. Any associated fraud alerts or suspicious verification history.\n"
        f"Provide a structured verdict and recommendation."
    )


@server.prompt()
def fraud_investigation_brief() -> str:
    """Prompt template for triaging unresolved fraud alerts."""
    return (
        "You are an anomaly detection and security auditor for the CertiTrust government registry.\n"
        "Call the `list_fraud_alerts` tool to fetch all unresolved fraud alerts.\n"
        "For each high or critical severity alert:\n"
        "1. Identify the suspicious activity (tampering, invalid signature, brute-force lookup).\n"
        "2. Examine the certificate details if available.\n"
        "3. Provide root-cause analysis and recommend whether to revoke or dismiss."
    )


# ---------------------------------------------------------------------------
# Server Entrypoint
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="CertiTrust Model Context Protocol (MCP) Server"
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "streamable-http", "sse"],
        default="stdio",
        help="MCP transport protocol: 'stdio' (default), 'streamable-http', or 'sse'.",
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host to bind for HTTP/SSE transports (default: 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to listen on for HTTP/SSE transports (default: 8000).",
    )
    parser.add_argument(
        "--path",
        default="/mcp",
        help="Path for streamable-http endpoint (default: /mcp).",
    )
    args = parser.parse_args()

    logger.info(f"Starting CertiTrust MCP server using '{args.transport}' transport...")

    if args.transport == "stdio":
        server.run(transport="stdio")
    elif args.transport == "streamable-http":
        server.run(
            transport="streamable-http",
            host=args.host,
            port=args.port,
            streamable_http_path=args.path,
        )
    elif args.transport == "sse":
        server.run(
            transport="sse",
            host=args.host,
            port=args.port,
        )


if __name__ == "__main__":
    main()

