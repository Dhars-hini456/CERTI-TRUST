document.querySelectorAll("#manualTabs .nav-link").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#manualTabs .nav-link").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("mtab-number").classList.add("d-none");
    document.getElementById("mtab-token").classList.add("d-none");
    document.getElementById("mtab-" + btn.dataset.mtab).classList.remove("d-none");
  });
});

function statusVisual(result) {
  const good = ["VERIFIED_ORIGINAL", "VERIFIED_OFFICIAL_REISSUE"];
  const bad = ["TAMPERED_MODIFIED", "FORGED_INVALID"];
  const warn = ["EXPIRED", "REVOKED", "PENDING_VERIFICATION"];
  if (good.includes(result)) return { cls: "status-good", icon: "✅" };
  if (bad.includes(result)) return { cls: "status-bad", icon: "⚠️" };
  if (warn.includes(result)) return { cls: "status-warn", icon: "⏱️" };
  return { cls: "status-neutral", icon: "❓" };
}

function renderResult(data) {
  const container = document.getElementById("resultContainer");
  const visual = statusVisual(data.result);
  let certBlock = "";
  if (data.certificate) {
    const c = data.certificate;
    certBlock = `
      <div class="ct-card mt-3"><div class="card-body">
        <div class="row g-3">
          <div class="col-md-6"><p class="small text-muted mb-1">Certificate Number</p><p class="fw-bold">${c.certificate_number}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Certificate Type</p><p class="fw-bold">${c.certificate_type}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Applicant</p><p class="fw-bold">${c.applicant_name}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Issued By</p><p class="fw-bold">${c.issued_by}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Issue Date</p><p class="fw-bold">${c.issue_date}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Expiry Date</p><p class="fw-bold">${c.expiry_date || "N/A"}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Integrity Check</p><p class="fw-bold ${data.hash_valid ? "text-success" : "text-danger"}">${data.hash_valid === null ? "N/A" : data.hash_valid ? "✓ PASSED" : "✗ FAILED"}</p></div>
          <div class="col-md-6"><p class="small text-muted mb-1">Digital Signature</p><p class="fw-bold ${data.signature_valid ? "text-success" : "text-danger"}">${data.signature_valid === null ? "N/A" : data.signature_valid ? "✓ VALID" : "✗ INVALID"}</p></div>
        </div>
      </div></div>`;
  }
  container.innerHTML = `
    <div class="result-hero ${visual.cls}">
      <div class="status-icon">${visual.icon}</div>
      <h3 class="fw-bold mb-1">${data.label}</h3>
      <p class="mb-0">${data.reason}</p>
    </div>
    ${certBlock}
  `;
}

async function verifyByNumber() {
  const certificate_number = document.getElementById("certNumberInput").value.trim();
  if (!certificate_number) return ctToast("Enter a certificate number.", "warning");
  try {
    const data = await ctFetch("/api/verifier/verify", { method: "POST", body: JSON.stringify({ certificate_number, method: "CERTIFICATE_NUMBER" }) });
    renderResult(data);
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

async function verifyByToken() {
  const token = document.getElementById("tokenInput").value.trim();
  if (!token) return ctToast("Enter a verification token.", "warning");
  try {
    const data = await ctFetch("/api/verifier/verify", { method: "POST", body: JSON.stringify({ token, method: "TOKEN" }) });
    renderResult(data);
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

let html5QrCode;
document.getElementById("startScanBtn").addEventListener("click", async () => {
  const btn = document.getElementById("startScanBtn");
  if (!html5QrCode) html5QrCode = new Html5Qrcode("qr-reader");
  try {
    btn.disabled = true;
    btn.textContent = "Starting camera...";
    await html5QrCode.start(
      { facingMode: "environment" },
      { fps: 10, qrbox: 220 },
      (decodedText) => {
        const parts = decodedText.split("/verify/");
        const token = parts.length > 1 ? parts[1] : decodedText;
        html5QrCode.stop();
        btn.disabled = false;
        btn.textContent = "Start Camera Scan";
        window.location.href = "/verify/" + token;
      },
      () => {}
    );
    btn.textContent = "Scanning... point camera at QR code";
  } catch (err) {
    ctToast("Camera unavailable. Please use manual entry instead.", "warning");
    btn.disabled = false;
    btn.textContent = "Start Camera Scan";
  }
});
