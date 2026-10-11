"""
Tests for CertiTrust MCP server tools and functionality.
"""
import asyncio
from app.models import Certificate
from mcp_server import flask_app, server


def test_mcp_list_tools():
    """Ensure all core MCP tools are registered."""
    async def _run():
        tools = await server.list_tools()
        tool_names = [t.name for t in tools]

        expected = [
            "verify_certificate_record",
            "get_certificate_details",
            "get_certificate_version_history",
            "search_certificates",
            "list_certificate_types",
            "list_departments",
            "get_dashboard_analytics",
            "get_department_analytics",
            "list_pending_applications",
            "review_application",
            "list_fraud_alerts",
            "resolve_fraud_alert",
            "get_verification_audit_trail",
            "list_recent_verifications",
            "revoke_certificate_record",
        ]
        for exp in expected:
            assert exp in tool_names, f"Expected tool '{exp}' not found in MCP tools"

    asyncio.run(_run())


def test_mcp_list_resources():
    """Ensure MCP resources are registered and readable."""
    async def _run():
        resources = await server.list_resources()
        resource_uris = [r.uri for r in resources]

        assert "certitrust://stats" in resource_uris
        assert "certitrust://certificate-types" in resource_uris
        assert "certitrust://unresolved-alerts" in resource_uris

        stats_content = await server.read_resource("certitrust://stats")
        assert stats_content is not None
        assert len(stats_content) > 0

    asyncio.run(_run())


def test_mcp_list_prompts():
    """Ensure MCP prompts are registered."""
    async def _run():
        prompts = await server.list_prompts()
        prompt_names = [p.name for p in prompts]

        assert "audit_certificate" in prompt_names
        assert "fraud_investigation_brief" in prompt_names

        prompt_res = await server.get_prompt("audit_certificate", {"certificate_number": "INC-2026-0001"})
        assert "INC-2026-0001" in prompt_res.messages[0].content.text

    asyncio.run(_run())


def test_mcp_verify_certificate_record_tool():
    """Test verify_certificate_record tool against an existing certificate."""
    async def _run():
        with flask_app.app_context():
            cert = Certificate.query.filter_by(status="ACTIVE").first()
            assert cert is not None, "No active certificate in database"
            cert_num = cert.certificate_number

        result = await server.call_tool("verify_certificate_record", {"identifier": cert_num})
        assert not result.is_error
        content = result.content[0].text
        assert "VERIFIED" in content

    asyncio.run(_run())


def test_mcp_get_dashboard_analytics_tool():
    """Test get_dashboard_analytics tool."""
    async def _run():
        result = await server.call_tool("get_dashboard_analytics", {})
        assert not result.is_error
        assert "total_certificates" in result.content[0].text

    asyncio.run(_run())


def test_mcp_list_certificate_types_tool():
    """Test list_certificate_types tool."""
    async def _run():
        result = await server.call_tool("list_certificate_types", {})
        assert not result.is_error
        assert len(result.content[0].text) > 0

    asyncio.run(_run())


def test_mcp_search_certificates_tool():
    """Test search_certificates tool."""
    async def _run():
        result = await server.call_tool("search_certificates", {"query": "", "limit": 5})
        assert not result.is_error
        assert "certificates" in result.content[0].text

    asyncio.run(_run())


def test_mcp_get_certificate_version_history_tool():
    async def _run():
        with flask_app.app_context():
            cert = Certificate.query.first()
            assert cert is not None
            cert_num = cert.certificate_number

        result = await server.call_tool(
            "get_certificate_version_history", {"certificate_number": cert_num}
        )
        assert not result.is_error
        assert '"found": true' in result.content[0].text
        assert '"version_count"' in result.content[0].text

    asyncio.run(_run())


def test_mcp_get_department_analytics_tool():
    async def _run():
        with flask_app.app_context():
            cert = Certificate.query.filter(Certificate.department.isnot(None)).first()
            assert cert is not None
            department = cert.department

        result = await server.call_tool(
            "get_department_analytics", {"department": department}
        )
        assert not result.is_error
        assert '"total_certificates"' in result.content[0].text
        assert '"certificates_by_status"' in result.content[0].text

    asyncio.run(_run())


def test_mcp_list_recent_verifications_tool():
    async def _run():
        with flask_app.app_context():
            cert = Certificate.query.filter_by(status="ACTIVE").first()
            assert cert is not None
            cert_num = cert.certificate_number

        await server.call_tool(
            "verify_certificate_record", {"identifier": cert_num}
        )
        result = await server.call_tool("list_recent_verifications", {"limit": 5})
        assert not result.is_error
        assert cert_num in result.content[0].text
        assert "ip_address" not in result.content[0].text

    asyncio.run(_run())


def test_mcp_get_verification_audit_trail_uses_model_timestamp():
    async def _run():
        with flask_app.app_context():
            cert = Certificate.query.filter_by(status="ACTIVE").first()
            assert cert is not None
            cert_num = cert.certificate_number

        await server.call_tool(
            "verify_certificate_record", {"identifier": cert_num}
        )
        result = await server.call_tool(
            "get_verification_audit_trail",
            {"certificate_number": cert_num},
        )
        assert not result.is_error
        assert "verified_at" in result.content[0].text

    asyncio.run(_run())

