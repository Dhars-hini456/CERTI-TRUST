# CertiTrust

**Real-Time Government Certificate Verification, Duplicate Detection and Monitoring System**

> ⚠️ **This is a hackathon demonstration project.** All citizens, officers, departments and certificates you see in the demo data are fictional. CertiTrust does not integrate with any real government system, and nothing here should be treated as an authentic government record.

---

## 1. Project Overview

CertiTrust is a full-stack web platform that lets a government department **issue, monitor and verify** certificates (income, caste, residence, birth, death, disability, legal heir, and more) with a tamper-evident, QR-based verification flow.

### Problem Statement
Paper government certificates are trivially photocopied, edited, or forged, and there is no fast, reliable way for a college, bank, or employer to check whether a certificate handed to them is genuine — without calling the issuing office and waiting days.

### Solution
Every certificate CertiTrust issues is:
1. Hashed (SHA-256) from its core fields,
2. Digitally signed with a department private key,
3. Bound to a single-use, secure QR verification token,
4. Instantly checkable by anyone, with a clear one-word-style verdict:
   `VERIFIED – ORIGINAL`, `VERIFIED – OFFICIAL REISSUE`, `TAMPERED / MODIFIED`,
   `FORGED / INVALID`, `NOT FOUND`, `EXPIRED`, `REVOKED`, or `PENDING VERIFICATION`.

Crucially, **an official duplicate is not automatically treated as fake.** Reissues are versioned and clearly labelled as official reissues.

---

## 2. Key Features

- **Four role-based portals**: Citizen, Government Officer, Verifier/Institution, Administrator
- **Configurable certificate types** — add new certificate types without touching code
- **Application workflow**: submit → document verification → officer review → approve/reject → issue
- **QR-code issuance and camera-based scanning** (via `html5-qrcode` in the browser)
- **SHA-256 tamper detection** and **RSA digital signatures** (via the `cryptography` library)
- **Official reissue / duplicate versioning**, distinct from fraud
- **Fraud & anomaly detection engine** with severity-graded alerts
- **Real-time monitoring dashboard** with Chart.js (issuance trends, verification outcomes, department stats, suspicious activity)
- **Verification logs / audit trail**
- **PDF certificate generation** (ReportLab) with embedded QR code
- **In-app notifications**, with a live notification bell in the navbar
- **Dark / light theme toggle**, persisted per-browser
- **Searchable, paginated tables** across officer, admin, alerts and history views
- **One-click CSV export** for applications, certificates, users, verification logs and fraud alerts
- **In-app QR preview modal** — view and open any certificate's QR without leaving the page
- **Animated live stats** on the public landing page (certificates issued, verifications run, etc.)
- **Automated tests** (pytest)

---

## 3. Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML5, CSS3, JavaScript, Bootstrap 5, Chart.js, html5-qrcode |
| Backend | Python 3, Flask, Flask-SQLAlchemy |
| Database | SQLite by default (zero config) — MySQL supported via XAMPP |
| Security | Werkzeug password hashing, SHA-256, RSA-PSS digital signatures, role-based access control |
| PDF | ReportLab |
| QR | `qrcode` (generation), `html5-qrcode` (browser scanning) |
| Testing | pytest |

---

## 4. Architecture

```
Browser (Bootstrap 5 + Chart.js + html5-qrcode)
        │  fetch() / form POST
        ▼
Flask App (Blueprints: pages, auth, citizen, officer, verifier, admin, api, verify)
        │
        ├── services/  certificate_service.py   (issue / reissue / revoke)
        │              verification_service.py  (the verification algorithm)
        ├── utils/      hashing.py   (SHA-256)
        │              signature.py (RSA sign/verify)
        │              qr_util.py   (QR generation)
        │              pdf_util.py  (certificate PDF)
        ▼
SQLAlchemy ORM
        ▼
SQLite (default) or MySQL (via XAMPP)
```

Role-based access is enforced with `@login_required` / `@role_required(...)` decorators (see `app/utils/decorators.py`) backed by Flask sessions — no plaintext passwords are ever stored (Werkzeug `generate_password_hash` / `check_password_hash`).

---

## 5. Database Schema (summary)

`users`, `roles` (embedded as a `role` column on `users`), `departments`, `certificate_types`, `applications`, `application_documents`, `certificates`, `certificate_versions`, `verification_logs`, `fraud_alerts`, `notifications`, `audit_logs`.

See `database/schema.sql` for the full MySQL DDL (used only if you choose the MySQL/XAMPP path — see below). If you use the default SQLite setup, Flask-SQLAlchemy creates all tables automatically on first run from `app/models.py`.

---

## 6. Installation & Setup (Windows + VS Code)

### 6.1 Prerequisites
- Python 3.10+ installed and on PATH
- VS Code (with the Python extension)
- (Optional, only for the MySQL path) XAMPP with Apache + MySQL

### 6.2 Fastest path — SQLite (recommended for the hackathon demo)

Open the project folder in VS Code, then open a terminal (`` Ctrl+` ``) and run:

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python scripts\seed_data.py
python run.py
```

Then open **http://localhost:5000** in your browser.

That's it — no XAMPP or MySQL required. `DATABASE_URL` in `.env` defaults to a local `certitrust.db` SQLite file, which Flask-SQLAlchemy creates automatically.

### 6.3 Alternative path — MySQL via XAMPP

1. Start **Apache** and **MySQL** from the XAMPP Control Panel.
2. Open **phpMyAdmin** (`http://localhost/phpmyadmin`).
3. Create a new database named `certitrust`.
4. Import `database/schema.sql` (creates all tables).
5. Import `database/seed.sql` (seeds departments & certificate types only — see note in that file).
6. Copy `.env.example` to `.env` and uncomment/edit the MySQL `DATABASE_URL` line, e.g.:
   ```
   DATABASE_URL=mysql+pymysql://root:@localhost:3306/certitrust
   ```
7. Install the MySQL driver as well: `pip install pymysql`
8. Run `python scripts\seed_data.py` to create demo users, applications and certificates (these need runtime-generated hashes/signatures/QR codes, so they're seeded via this Python script rather than raw SQL).
9. Run `python run.py`.

### 6.4 macOS / Linux
Replace `venv\Scripts\activate` with `source venv/bin/activate`, and `copy` with `cp`. Everything else is identical.

### 6.5 Deploy to the web — Render (free, optional)

The easiest way to put the hackathon demo online is [Render](https://render.com). This repo ships a `Procfile` and `render.yaml`, so deployment is mostly clicking:

1. Make sure this project is pushed to GitHub (`git push origin main`).
2. Go to **https://render.com** → sign up/log in → **New** → **Blueprint** → connect your GitHub account → select the **CERTI-TRUST** repo.
3. Render auto-detects `render.yaml` — click **Apply / Create Resources** (it provisions a free web service named `certitrust`).
4. Wait for the first build + deploy (~2–4 min). Open your live app at **https://certitrust.onrender.com**.
5. Seed the demo data once: open the Render dashboard → your service → **Shell** tab and run:
   ```bash
   python scripts/seed_data.py
   ```

`render.yaml` already sets `FLASK_SECRET_KEY` (generated#`, `FLASK_DEBUG=False` and `BASE_VERIFY_URL=https://certitrust.onrender.com/verify` automatically. If you deploy manually (New → Web Service) instead, set those three in **Environment** yourself.

> ⚠️ **Render free tier uses a temporary disk** — SQLite DB, uploads/, QR files and generated PDFs reset on each new deploy. Simply re-run `python scripts/seed_data.py` via the Shell tab after redeploys. For live data, attach a managed PostgreSQL/MySQL service and change `DATABASE_URL`.
---

## 7. Environment Variables

See `.env.example`. Never commit a real `.env` file with production secrets. Key variables:

| Variable | Purpose |
|---|---|
| `FLASK_SECRET_KEY` | Flask session signing key |
| `FLASK_DEBUG` | `True` for local development |
| `DATABASE_URL` | SQLAlchemy connection string (SQLite by default) |
| `BASE_VERIFY_URL` | Base URL embedded inside generated QR codes |
| `DEMO_PASSWORD` | Password used for all demo accounts created by `scripts/seed_data.py` |

---

## 8. Demo Accounts

All demo accounts use the password: **`Demo@1234`** (configurable via `DEMO_PASSWORD` in `.env`).

| Role | Email |
|---|---|
| Administrator | admin@demo.local |
| Officer | officer@demo.local |
| Verifier | verifier@demo.local |
| Citizen | citizen@demo.local |

**These credentials are for local demonstration only.** Do not reuse this pattern in any real deployment.

---

## 9. Generating QR Codes

QR codes are generated automatically the moment an officer issues (or reissues) a certificate — no manual step required. Each QR encodes a URL of the form:

```
http://localhost:5000/verify/<secure-token>
```

The token is a random, unguessable string (`secrets.token_urlsafe`), never personal data. Generated images are stored under `app/static/qr/`.

---

## 10. REST API Endpoints

See `API_DOCUMENTATION.md` for full request/response details. Summary:

```
POST /api/auth/register
POST /api/auth/login
POST /api/auth/logout

GET  /api/citizen/applications
POST /api/citizen/applications
POST /api/citizen/applications/<id>/documents
GET  /api/citizen/certificates

GET  /api/officer/applications
POST /api/officer/applications/<id>/approve
POST /api/officer/applications/<id>/reject
POST /api/officer/applications/<id>/issue
POST /api/officer/certificates/<id>/reissue
POST /api/officer/certificates/<id>/revoke
GET  /api/officer/certificates/<id>/download
GET  /api/officer/certificates

POST /api/verifier/verify
GET  /api/verifier/history

GET  /api/admin/users            POST /api/admin/users
GET  /api/admin/departments      POST /api/admin/departments
GET  /api/admin/certificate-types  POST /api/admin/certificate-types
GET  /api/admin/certificates
GET  /api/admin/fraud-alerts     POST /api/admin/fraud-alerts/<id>/resolve

GET  /api/verify/<token>
POST /api/verify/certificate-number
GET  /api/dashboard
GET  /api/analytics
GET  /api/verification-logs
GET  /api/notifications

GET  /verify                (public verification page)
GET  /verify/<token>         (QR redirect target)
POST /verify/lookup          (manual form lookup)
```

---

## 11. Testing

```powershell
pip install -r requirements.txt
pytest -v
```

Tests spin up an isolated temporary SQLite database and temporary file folders, so they never touch your real local data. Covered: registration, login, certificate issuance, QR generation, valid verification, unknown certificate, tamper detection, invalid-signature detection, official reissue (not treated as fake), revocation, expiry, and role-based access control.

---

## 12. Hackathon Demo Script (5 minutes)

1. **Citizen**: log in as `citizen@demo.local`, submit a new certificate application.
2. **Officer**: log in as `officer@demo.local`, approve the application, then click **Issue Certificate** (this hashes, signs, QR-codes and PDF-generates the certificate automatically).
3. **Verifier**: log in as `verifier@demo.local`, open **Verifier Dashboard**, and either scan the QR code (camera) or type the certificate number → shows **VERIFIED – ORIGINAL**.
4. Back on the **Officer Dashboard**, click **Reissue** on that certificate with a reason like "lost original" → verify the *new* certificate number → shows **VERIFIED – OFFICIAL REISSUE** (not flagged as fake).
5. Run `python scripts/seed_data.py` beforehand to get pre-loaded tampered/expired/revoked demo certificates, or manually edit a certificate's applicant name directly in the database to simulate tampering, then verify it → shows **TAMPERED / MODIFIED**.
6. Open the **Officer/Admin Dashboard** to show live Chart.js analytics, then **Fraud Alerts** and **Verification History** to show the full audit trail.

---

## 13. Troubleshooting

| Problem | Fix |
|---|---|
| `ModuleNotFoundError` on startup | Make sure you activated the virtual environment and ran `pip install -r requirements.txt` |
| Port 5000 already in use | Edit `run.py` and change the port, e.g. `app.run(port=5001)` |
| QR codes not appearing | Check that `app/static/qr/` exists and is writable; it's created automatically on first run |
| Camera scanner doesn't start | Browsers only allow camera access on `localhost` or HTTPS — use `http://localhost:5000`, not `http://127.0.0.1:5000` on some browsers, and grant camera permission when prompted |
| MySQL connection errors | Confirm Apache + MySQL are running in XAMPP, the `certitrust` database exists, and you installed `pymysql` |
| Login fails with correct demo password | Re-run `python scripts/seed_data.py` — it resets and reseeds the whole database |

---

## 14. Limitations (by design, for this demo)

- Document-upload verification reads only the certificate number you type — no OCR or AI-based forgery detection is claimed or implemented (the architecture leaves room for this to be added later).
- Digital signature keys are generated locally on first run (`config/dev_private_key.pem` / `dev_public_key.pem`) purely for demonstration — **a real government deployment would use managed PKI / an HSM**, never keys sitting on a web server's disk.
- Email/SMS notifications are not wired to a real provider; only in-app notifications are implemented.
- No integration with Aadhaar, DigiLocker, or any other real government system is implemented or claimed.

## 15. Future Enhancements

OCR-based document verification, AI-assisted forgery detection, managed PKI/HSM signing, Aadhaar/identity integration, blockchain-backed audit trail, DigiLocker integration, SMS/email gateways, a native mobile app, and multi-state/multi-department deployment.

---

## 16. License

See `LICENSE`. Provided as-is for hackathon/educational demonstration purposes.
