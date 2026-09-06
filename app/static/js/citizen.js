document.querySelectorAll("#citizenTabs .nav-link").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#citizenTabs .nav-link").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("tab-applications").classList.add("d-none");
    document.getElementById("tab-certificates").classList.add("d-none");
    document.getElementById("tab-" + btn.dataset.tab).classList.remove("d-none");
  });
});

function statusBadge(status) {
  return `<span class="badge-status ${ctStatusBadgeClass(status)}">${status.replace(/_/g, " ")}</span>`;
}

async function loadApplications() {
  const tbody = document.getElementById("applicationsBody");
  try {
    const apps = await ctFetch("/api/citizen/applications");
    if (apps.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5">${ctEmptyState("No applications yet. Click '+ New Application' to get started.", "📄")}</td></tr>`;
      return;
    }
    tbody.innerHTML = apps
      .map(
        (a) => `
      <tr>
        <td class="fw-semibold">${a.application_number}</td>
        <td>${a.certificate_type}</td>
        <td>${statusBadge(a.status)}${a.rejection_reason ? `<div class="small text-danger mt-1">${a.rejection_reason}</div>` : ""}</td>
        <td>${a.created_at}</td>
        <td></td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-danger text-center py-3">${err.message}</td></tr>`;
  }
}

async function loadCertificates() {
  const grid = document.getElementById("certificatesGrid");
  try {
    const certs = await ctFetch("/api/citizen/certificates");
    if (certs.length === 0) {
      grid.innerHTML = `<div class="col-12">${ctEmptyState("No certificates issued yet.", "🎓")}</div>`;
      return;
    }
    grid.innerHTML = certs
      .map(
        (c) => `
      <div class="col-md-6 col-lg-4">
        <div class="ct-card h-100"><div class="card-body">
          <div class="d-flex justify-content-between align-items-start mb-2">
            <h6 class="fw-bold mb-0">${c.certificate_type}</h6>
            ${statusBadge(c.status)}
          </div>
          <p class="small text-muted mb-1">Certificate Number</p>
          <p class="fw-semibold mb-2">${c.certificate_number}</p>
          <p class="small text-muted mb-3">Issued: ${c.issue_date} &middot; Expires: ${c.expiry_date || "N/A"}</p>
          <div class="d-flex gap-2">
            <button class="btn btn-sm btn-outline-primary flex-fill" onclick="showQrPreview('${c.qr_token}', '${c.certificate_number}')">View QR</button>
            <a class="btn btn-sm btn-ct-primary flex-fill" href="/api/officer/certificates/${c.id}/download">Download PDF</a>
          </div>
        </div></div>
      </div>`
      )
      .join("");
  } catch (err) {
    grid.innerHTML = `<div class="col-12 text-danger text-center">${err.message}</div>`;
  }
}

function showQrPreview(token, certNumber) {
  document.getElementById("qrPreviewImg").src = `/static/qr/${token}.png`;
  document.getElementById("qrPreviewLink").href = `/verify/${token}`;
  document.getElementById("qrPreviewLabel").textContent = certNumber;
  new bootstrap.Modal(document.getElementById("qrPreviewModal")).show();
}

document.getElementById("applyForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    certificate_type_id: document.getElementById("certificate_type_id").value,
    applicant_name: document.getElementById("applicant_name").value.trim(),
    date_of_birth: document.getElementById("date_of_birth").value,
    purpose: document.getElementById("purpose").value.trim(),
    address: document.getElementById("address").value.trim(),
  };
  try {
    const res = await ctFetch("/api/citizen/applications", { method: "POST", body: JSON.stringify(payload) });

    const fileInput = document.getElementById("documentFile");
    if (fileInput.files.length > 0) {
      const appsList = await ctFetch("/api/citizen/applications");
      const created = appsList.find((a) => a.application_number === res.application_number);
      if (created) {
        const fd = new FormData();
        fd.append("file", fileInput.files[0]);
        await fetch(`/api/citizen/applications/${created.id}/documents`, { method: "POST", body: fd });
      }
    }

    ctToast("Application submitted successfully!", "success");
    bootstrap.Modal.getInstance(document.getElementById("applyModal")).hide();
    document.getElementById("applyForm").reset();
    loadApplications();
  } catch (err) {
    ctToast(err.message, "danger");
  }
});

loadApplications();
loadCertificates();
