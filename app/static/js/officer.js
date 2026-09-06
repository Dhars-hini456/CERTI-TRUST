document.querySelectorAll("#officerTabs .nav-link").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#officerTabs .nav-link").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-applications").classList.add("d-none");
    document.getElementById("tab-certificates").classList.add("d-none");
    document.getElementById("tab-" + btn.dataset.tab).classList.remove("d-none");
  });
});

function statusBadge(status) {
  return `<span class="badge-status ${ctStatusBadgeClass(status)}">${status.replace(/_/g, " ")}</span>`;
}

async function loadStats() {
  try {
    const s = await ctFetch("/api/dashboard");
    document.getElementById("statTotal").textContent = s.total_certificates;
    document.getElementById("statVerified").textContent = s.verified_certificates;
    document.getElementById("statPending").textContent = s.pending_applications;
    document.getElementById("statSuspicious").textContent = s.suspicious_certificates;
    document.getElementById("statReissued").textContent = s.reissued_certificates;
    document.getElementById("statRevoked").textContent = s.revoked_certificates;
    document.getElementById("statExpired").textContent = s.expired_certificates;
    document.getElementById("statVerifications").textContent = s.total_verification_requests;
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

let charts = {};
function upsertChart(id, config) {
  if (charts[id]) charts[id].destroy();
  charts[id] = new Chart(document.getElementById(id), config);
}

async function loadAnalytics() {
  try {
    const a = await ctFetch("/api/analytics");

    upsertChart("chartByMonth", {
      type: "line",
      data: {
        labels: a.certificates_by_month.labels,
        datasets: [{ label: "Certificates Issued", data: a.certificates_by_month.values, borderColor: "#7c3aed", backgroundColor: "rgba(124,58,237,.15)", fill: true, tension: 0.35 }],
      },
      options: { plugins: { legend: { display: false } }, responsive: true },
    });

    const vrLabels = Object.keys(a.verification_results);
    const vrValues = Object.values(a.verification_results);
    upsertChart("chartVerificationResults", {
      type: "doughnut",
      data: { labels: vrLabels.length ? vrLabels : ["No data yet"], datasets: [{ data: vrValues.length ? vrValues : [1], backgroundColor: ["#10b981", "#3b82f6", "#ef4444", "#f59e0b", "#94a3b8", "#7c3aed", "#ec4899"] }] },
      options: { responsive: true },
    });

    const ctLabels = Object.keys(a.certificate_types);
    const ctValues = Object.values(a.certificate_types);
    upsertChart("chartCertTypes", {
      type: "bar",
      data: { labels: ctLabels.length ? ctLabels : ["No data yet"], datasets: [{ label: "Certificates", data: ctValues.length ? ctValues : [0], backgroundColor: "#06b6d4" }] },
      options: { plugins: { legend: { display: false } }, responsive: true },
    });

    upsertChart("chartSuspiciousTrend", {
      type: "bar",
      data: { labels: a.suspicious_trend.labels, datasets: [{ label: "Fraud Alerts", data: a.suspicious_trend.values, backgroundColor: "#ef4444" }] },
      options: { plugins: { legend: { display: false } }, responsive: true },
    });
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

/* ---------------------------------------------------------------- */
/* Applications: search + pagination                                 */
/* ---------------------------------------------------------------- */
let allApplications = [];
let appPage = 1;
const APP_PAGE_SIZE = 8;

function renderApplicationsTable() {
  const tbody = document.getElementById("officerApplicationsBody");
  const query = (document.getElementById("appSearchInput")?.value || "").toLowerCase();
  const filtered = allApplications.filter(
    (a) =>
      a.application_number.toLowerCase().includes(query) ||
      a.citizen_name.toLowerCase().includes(query) ||
      a.certificate_type.toLowerCase().includes(query) ||
      a.status.toLowerCase().includes(query)
  );

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6">${ctEmptyState("No matching applications found.", "📄")}</td></tr>`;
    ctRenderPagination(document.getElementById("appPagination"), 0, 1, APP_PAGE_SIZE, () => {});
    return;
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / APP_PAGE_SIZE));
  if (appPage > totalPages) appPage = totalPages;
  const pageItems = ctPaginate(filtered, appPage, APP_PAGE_SIZE);

  tbody.innerHTML = pageItems
    .map((a) => {
      let actions = "";
      if (a.status === "SUBMITTED" || a.status === "UNDER_REVIEW") {
        actions = `
          <button class="btn btn-sm btn-outline-success me-1" onclick="approveApp(${a.id})">Approve</button>
          <button class="btn btn-sm btn-outline-danger" onclick="openReject(${a.id})">Reject</button>`;
      } else if (a.status === "APPROVED") {
        actions = `<button class="btn btn-sm btn-ct-primary" onclick="issueCert(${a.id})">Issue Certificate</button>`;
      } else {
        actions = `<span class="text-muted small">No action needed</span>`;
      }
      return `<tr>
        <td class="fw-semibold">${a.application_number}</td>
        <td>${a.citizen_name}</td>
        <td>${a.certificate_type}</td>
        <td>${statusBadge(a.status)}</td>
        <td>${a.created_at}</td>
        <td>${actions}</td>
      </tr>`;
    })
    .join("");

  ctRenderPagination(document.getElementById("appPagination"), filtered.length, appPage, APP_PAGE_SIZE, (p) => {
    appPage = p;
    renderApplicationsTable();
  });
}

async function loadOfficerApplications() {
  const tbody = document.getElementById("officerApplicationsBody");
  try {
    allApplications = await ctFetch("/api/officer/applications");
    appPage = 1;
    renderApplicationsTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger text-center py-3">${err.message}</td></tr>`;
  }
}

/* ---------------------------------------------------------------- */
/* Certificates: search + pagination + QR preview + CSV export       */
/* ---------------------------------------------------------------- */
let allCertificates = [];
let certPage = 1;
const CERT_PAGE_SIZE = 8;

function renderCertificatesTable() {
  const tbody = document.getElementById("officerCertificatesBody");
  const query = (document.getElementById("certSearchInput")?.value || "").toLowerCase();
  const filtered = allCertificates.filter(
    (c) =>
      c.certificate_number.toLowerCase().includes(query) ||
      c.applicant_name.toLowerCase().includes(query) ||
      c.certificate_type.toLowerCase().includes(query) ||
      c.status.toLowerCase().includes(query)
  );

  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6">${ctEmptyState("No matching certificates found.", "🎓")}</td></tr>`;
    ctRenderPagination(document.getElementById("certPagination"), 0, 1, CERT_PAGE_SIZE, () => {});
    return;
  }

  const totalPages = Math.max(1, Math.ceil(filtered.length / CERT_PAGE_SIZE));
  if (certPage > totalPages) certPage = totalPages;
  const pageItems = ctPaginate(filtered, certPage, CERT_PAGE_SIZE);

  tbody.innerHTML = pageItems
    .map((c) => {
      let actions = `<button class="btn btn-sm btn-outline-primary me-1" onclick="showQrPreview('${c.qr_token || ""}', '${c.certificate_number}')">QR</button>`;
      if (c.status === "ACTIVE") {
        actions += `
          <button class="btn btn-sm btn-outline-secondary me-1" onclick="openReissue(${c.id})">Reissue</button>
          <button class="btn btn-sm btn-outline-danger" onclick="openRevoke(${c.id})">Revoke</button>`;
      }
      return `<tr>
        <td class="fw-semibold">${c.certificate_number}</td>
        <td>${c.applicant_name}</td>
        <td>${c.certificate_type}</td>
        <td>${statusBadge(c.status)}</td>
        <td>v${c.version_number}</td>
        <td>${actions}</td>
      </tr>`;
    })
    .join("");

  ctRenderPagination(document.getElementById("certPagination"), filtered.length, certPage, CERT_PAGE_SIZE, (p) => {
    certPage = p;
    renderCertificatesTable();
  });
}

async function loadOfficerCertificates() {
  const tbody = document.getElementById("officerCertificatesBody");
  try {
    allCertificates = await ctFetch("/api/officer/certificates");
    certPage = 1;
    renderCertificatesTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger text-center py-3">${err.message}</td></tr>`;
  }
}

function showQrPreview(token, certNumber) {
  if (!token) {
    ctToast("No QR code available for this certificate.", "warning");
    return;
  }
  document.getElementById("qrPreviewImg").src = `/static/qr/${token}.png`;
  document.getElementById("qrPreviewLink").href = `/verify/${token}`;
  document.getElementById("qrPreviewLabel").textContent = certNumber;
  new bootstrap.Modal(document.getElementById("qrPreviewModal")).show();
}

function exportApplicationsCsv() {
  ctExportCsv("certitrust_applications.csv", allApplications, [
    { key: "application_number", label: "Application Number" },
    { key: "citizen_name", label: "Citizen" },
    { key: "certificate_type", label: "Certificate Type" },
    { key: "status", label: "Status" },
    { key: "created_at", label: "Submitted" },
  ]);
}

function exportCertificatesCsv() {
  ctExportCsv("certitrust_certificates.csv", allCertificates, [
    { key: "certificate_number", label: "Certificate Number" },
    { key: "applicant_name", label: "Applicant" },
    { key: "certificate_type", label: "Certificate Type" },
    { key: "status", label: "Status" },
    { key: "version_number", label: "Version" },
  ]);
}

document.getElementById("appSearchInput")?.addEventListener("input", () => {
  appPage = 1;
  renderApplicationsTable();
});
document.getElementById("certSearchInput")?.addEventListener("input", () => {
  certPage = 1;
  renderCertificatesTable();
});

async function approveApp(id) {
  try {
    await ctFetch(`/api/officer/applications/${id}/approve`, { method: "POST" });
    ctToast("Application approved.", "success");
    loadOfficerApplications();
    loadStats();
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

function openReject(id) {
  document.getElementById("rejectApplicationId").value = id;
  new bootstrap.Modal(document.getElementById("rejectModal")).show();
}
async function confirmReject() {
  const id = document.getElementById("rejectApplicationId").value;
  const reason = document.getElementById("rejectReason").value.trim();
  try {
    await ctFetch(`/api/officer/applications/${id}/reject`, { method: "POST", body: JSON.stringify({ reason }) });
    ctToast("Application rejected.", "warning");
    bootstrap.Modal.getInstance(document.getElementById("rejectModal")).hide();
    loadOfficerApplications();
    loadStats();
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

async function issueCert(id) {
  try {
    const res = await ctFetch(`/api/officer/applications/${id}/issue`, { method: "POST" });
    ctToast(`Certificate ${res.certificate_number} issued & digitally signed!`, "success");
    loadOfficerApplications();
    loadOfficerCertificates();
    loadStats();
    loadAnalytics();
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

function openReissue(id) {
  document.getElementById("reissueCertificateId").value = id;
  new bootstrap.Modal(document.getElementById("reissueModal")).show();
}
async function confirmReissue() {
  const id = document.getElementById("reissueCertificateId").value;
  const reason = document.getElementById("reissueReason").value.trim();
  try {
    const res = await ctFetch(`/api/officer/certificates/${id}/reissue`, { method: "POST", body: JSON.stringify({ reason }) });
    ctToast(`Official reissue ${res.certificate_number} (v${res.version_number}) created.`, "success");
    bootstrap.Modal.getInstance(document.getElementById("reissueModal")).hide();
    loadOfficerCertificates();
    loadStats();
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

function openRevoke(id) {
  document.getElementById("revokeCertificateId").value = id;
  new bootstrap.Modal(document.getElementById("revokeModal")).show();
}
async function confirmRevoke() {
  const id = document.getElementById("revokeCertificateId").value;
  const reason = document.getElementById("revokeReason").value.trim();
  try {
    await ctFetch(`/api/officer/certificates/${id}/revoke`, { method: "POST", body: JSON.stringify({ reason }) });
    ctToast("Certificate revoked.", "warning");
    bootstrap.Modal.getInstance(document.getElementById("revokeModal")).hide();
    loadOfficerCertificates();
    loadStats();
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

loadStats();
loadAnalytics();
loadOfficerApplications();
loadOfficerCertificates();
