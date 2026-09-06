# CertiTrust API Documentation

All endpoints return JSON unless stated otherwise. Authenticated endpoints rely on a Flask session cookie set by `/api/auth/login` — log in first, then reuse the same client/session for subsequent requests.

Base URL (local): `http://localhost:5000`

---

## Authentication

### `POST /api/auth/register`
Registers a new **citizen** account (other roles are provisioned by an admin).

**Body**
```json
{ "full_name": "Ananya Sharma", "email": "ananya@example.com", "password": "Demo@1234", "phone": "9812345678" }
```
**Responses**: `201 Created` / `400 Bad Request` / `409 Conflict` (email already in use)

### `POST /api/auth/login`
**Body**: `{ "email": "...", "password": "..." }`
**200 OK**
```json
{ "message": "Login successful.", "role": "citizen", "full_name": "Ananya Sharma", "redirect": "/citizen-dashboard" }
```
**401 Unauthorized** on bad credentials.

### `POST /api/auth/logout`
Clears the session. `200 OK`.

---

## Citizen

All routes require an authenticated **citizen** session.

### `GET /api/citizen/applications`
List the logged-in citizen's own applications.

### `POST /api/citizen/applications`
```json
{ "certificate_type_id": 2, "applicant_name": "Ananya Sharma", "date_of_birth": "1998-05-10", "address": "...", "purpose": "College admission" }
```

### `POST /api/citizen/applications/<id>/documents`
`multipart/form-data` with a `file` field (PDF/PNG/JPG, max 8 MB).

### `GET /api/citizen/certificates`
List certificates issued against the citizen's own applications.

---

## Officer

Requires an **officer** or **admin** session.

### `GET /api/officer/applications?status=SUBMITTED`
List applications, optionally filtered by status.

### `POST /api/officer/applications/<id>/approve`
### `POST /api/officer/applications/<id>/reject`
```json
{ "reason": "Documents incomplete" }
```
### `POST /api/officer/applications/<id>/issue`
Issues (hashes, signs, QR-codes, PDF-generates) the certificate for an **APPROVED** application.

### `POST /api/officer/certificates/<id>/reissue`
```json
{ "reason": "Original certificate lost by applicant" }
```
Creates a new, versioned "official reissue" certificate. The old certificate is marked `SUPERSEDED`, not deleted.

### `POST /api/officer/certificates/<id>/revoke`
```json
{ "reason": "Fraudulent documents discovered on audit" }
```

### `GET /api/officer/certificates/<id>/download`
Downloads the certificate PDF.

### `GET /api/officer/certificates`
List recent certificates.

---

## Verifier

Requires a **verifier**, **officer**, or **admin** session.

### `POST /api/verifier/verify`
```json
{ "certificate_number": "INC-2026-000123" }
```
or
```json
{ "token": "abc123..." }
```

**200 OK**
```json
{
  "result": "VERIFIED_ORIGINAL",
  "label": "VERIFIED - ORIGINAL",
  "hash_valid": true,
  "signature_valid": true,
  "reason": "Certificate integrity and signature verified successfully.",
  "certificate": {
    "certificate_number": "INC-2026-000123",
    "certificate_type": "Income Certificate",
    "applicant_name": "Sample User",
    "issue_date": "15-08-2026",
    "expiry_date": "15-08-2027",
    "issued_by": "Revenue Department",
    "status": "ACTIVE",
    "version_number": 1
  }
}
```

Possible `result` values: `VERIFIED_ORIGINAL`, `VERIFIED_OFFICIAL_REISSUE`, `TAMPERED_MODIFIED`, `FORGED_INVALID`, `NOT_FOUND`, `EXPIRED`, `REVOKED`, `PENDING_VERIFICATION`.

### `GET /api/verifier/history`
The logged-in verifier's own recent verification attempts.

---

## Public Verification (no login required)

### `GET /verify`
Renders the public verification form (HTML).

### `GET /verify/<token>`
Renders the verification result page (HTML) — this is exactly what a scanned QR code opens.

### `POST /verify/lookup`
Form-encoded (`certificate_number` or `token`), renders the same result page (HTML).

### `GET /api/verify/<token>`
JSON equivalent of `GET /verify/<token>`.

### `POST /api/verify/certificate-number`
```json
{ "certificate_number": "INC-2026-000123" }
```
JSON equivalent for manual certificate-number lookups.

---

## Admin

Requires an **admin** session (certificate-type listing is also open to other logged-in roles for their own dropdowns).

### `GET /api/admin/users` &nbsp; `POST /api/admin/users`
```json
{ "full_name": "New Officer", "email": "newofficer@demo.local", "password": "Demo@1234", "role": "officer", "department": "Revenue Department" }
```

### `POST /api/admin/users/<id>/toggle-active`
Enables/disables a user account.

### `GET /api/admin/departments` &nbsp; `POST /api/admin/departments`
```json
{ "name": "Health Department", "code": "HLT", "description": "..." }
```

### `GET /api/admin/certificate-types` &nbsp; `POST /api/admin/certificate-types`
```json
{ "name": "Domicile Certificate", "code": "DOM", "department": "Revenue Department", "validity_days": 1825 }
```

### `GET /api/admin/certificates`
All certificates system-wide.

### `GET /api/admin/fraud-alerts` &nbsp; `POST /api/admin/fraud-alerts/<id>/resolve`
List and resolve fraud alerts.

---

## Dashboard & Analytics

Requires any authenticated session (`officer`/`admin` for the fuller picture, but the endpoints themselves only require login).

### `GET /api/public-stats`
No login required. Returns non-sensitive aggregate counts used to animate the public landing page.
```json
{ "total_certificates": 24, "total_verification_requests": 57, "certificate_types": 8, "departments": 4 }
```

### `GET /api/dashboard`
```json
{
  "total_certificates": 20,
  "issued_today": 2,
  "verified_certificates": 13,
  "pending_applications": 4,
  "reissued_certificates": 3,
  "revoked_certificates": 2,
  "expired_certificates": 2,
  "suspicious_certificates": 3,
  "total_verification_requests": 42
}
```

### `GET /api/analytics`
Returns chart-ready data: `certificates_by_month`, `verification_results`, `certificate_types`, `departments`, `suspicious_trend`, `application_status`.

### `GET /api/verification-logs`
Full verification/audit log (officer/admin/verifier).

### `GET /api/notifications` &nbsp; `POST /api/notifications/<id>/read`
The logged-in user's own in-app notifications.

---

## Error format

Errors are returned as:
```json
{ "error": "Human-readable message" }
```
with an appropriate HTTP status code (`400`, `401`, `403`, `404`, `409`, `413`).
