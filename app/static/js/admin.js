document.querySelectorAll("#adminTabs .nav-link").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll("#adminTabs .nav-link").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    ["users", "cert-types", "departments", "certificates"].forEach((t) =>
      document.getElementById("tab-" + t).classList.add("d-none")
    );
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
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

/* ---------------------------------------------------------------- */
/* Users: search + pagination                                        */
/* ---------------------------------------------------------------- */
let allUsers = [];
let userPage = 1;
const USER_PAGE_SIZE = 8;

function renderUsersTable() {
  const tbody = document.getElementById("usersBody");
  const query = (document.getElementById("userSearchInput")?.value || "").toLowerCase();
  const filtered = allUsers.filter(
    (u) => u.full_name.toLowerCase().includes(query) || u.email.toLowerCase().includes(query) || u.role.toLowerCase().includes(query)
  );
  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6">${ctEmptyState("No matching users found.", "👤")}</td></tr>`;
    ctRenderPagination(document.getElementById("userPagination"), 0, 1, USER_PAGE_SIZE, () => {});
    return;
  }
  const totalPages = Math.max(1, Math.ceil(filtered.length / USER_PAGE_SIZE));
  if (userPage > totalPages) userPage = totalPages;
  const pageItems = ctPaginate(filtered, userPage, USER_PAGE_SIZE);

  tbody.innerHTML = pageItems
    .map(
      (u) => `<tr>
      <td class="fw-semibold">${u.full_name}</td>
      <td>${u.email}</td>
      <td><span class="badge bg-secondary-subtle text-dark text-uppercase">${u.role}</span></td>
      <td>${u.department || "-"}</td>
      <td>${u.is_active ? '<span class="badge-status badge-active">ACTIVE</span>' : '<span class="badge-status badge-revoked">DISABLED</span>'}</td>
      <td><button class="btn btn-sm btn-outline-secondary" onclick="toggleUser(${u.id})">${u.is_active ? "Disable" : "Enable"}</button></td>
    </tr>`
    )
    .join("");

  ctRenderPagination(document.getElementById("userPagination"), filtered.length, userPage, USER_PAGE_SIZE, (p) => {
    userPage = p;
    renderUsersTable();
  });
}

async function loadUsers() {
  const tbody = document.getElementById("usersBody");
  try {
    allUsers = await ctFetch("/api/admin/users");
    userPage = 1;
    renderUsersTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-danger text-center">${err.message}</td></tr>`;
  }
}

function exportUsersCsv() {
  ctExportCsv("certitrust_users.csv", allUsers, [
    { key: "full_name", label: "Full Name" },
    { key: "email", label: "Email" },
    { key: "role", label: "Role" },
    { key: "department", label: "Department" },
    { key: "is_active", label: "Active" },
  ]);
}

async function toggleUser(id) {
  try {
    await ctFetch(`/api/admin/users/${id}/toggle-active`, { method: "POST" });
    loadUsers();
  } catch (err) {
    ctToast(err.message, "danger");
  }
}

/* ---------------------------------------------------------------- */
/* Certificate types & departments (small lists, no pagination)      */
/* ---------------------------------------------------------------- */
async function loadCertTypes() {
  const tbody = document.getElementById("certTypesBody");
  try {
    const types = await ctFetch("/api/admin/certificate-types");
    if (types.length === 0) {
      tbody.innerHTML = `<tr><td colspan="5">${ctEmptyState("No certificate types yet.", "📋")}</td></tr>`;
      return;
    }
    tbody.innerHTML = types
      .map(
        (t) => `<tr>
        <td class="fw-semibold">${t.name}</td><td>${t.code}</td><td>${t.department || "-"}</td>
        <td>${t.validity_days}</td>
        <td>${t.is_active ? '<span class="badge-status badge-active">ACTIVE</span>' : '<span class="badge-status badge-revoked">INACTIVE</span>'}</td>
      </tr>`
      )
      .join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="5" class="text-danger text-center">${err.message}</td></tr>`;
  }
}

async function loadDepartments() {
  const tbody = document.getElementById("departmentsBody");
  try {
    const depts = await ctFetch("/api/admin/departments");
    if (depts.length === 0) {
      tbody.innerHTML = `<tr><td colspan="2">${ctEmptyState("No departments yet.", "🏛️")}</td></tr>`;
      return;
    }
    tbody.innerHTML = depts.map((d) => `<tr><td class="fw-semibold">${d.name}</td><td>${d.code}</td></tr>`).join("");
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="2" class="text-danger text-center">${err.message}</td></tr>`;
  }
}

/* ---------------------------------------------------------------- */
/* All certificates: search + pagination + export                    */
/* ---------------------------------------------------------------- */
let allCertsAdmin = [];
let adminCertPage = 1;
const ADMIN_CERT_PAGE_SIZE = 8;

function renderAllCertificatesTable() {
  const tbody = document.getElementById("allCertificatesBody");
  const query = (document.getElementById("certAdminSearchInput")?.value || "").toLowerCase();
  const filtered = allCertsAdmin.filter(
    (c) => c.certificate_number.toLowerCase().includes(query) || c.applicant_name.toLowerCase().includes(query) || c.status.toLowerCase().includes(query)
  );
  if (filtered.length === 0) {
    tbody.innerHTML = `<tr><td colspan="4">${ctEmptyState("No matching certificates found.", "🎓")}</td></tr>`;
    ctRenderPagination(document.getElementById("adminCertPagination"), 0, 1, ADMIN_CERT_PAGE_SIZE, () => {});
    return;
  }
  const totalPages = Math.max(1, Math.ceil(filtered.length / ADMIN_CERT_PAGE_SIZE));
  if (adminCertPage > totalPages) adminCertPage = totalPages;
  const pageItems = ctPaginate(filtered, adminCertPage, ADMIN_CERT_PAGE_SIZE);

  tbody.innerHTML = pageItems
    .map((c) => `<tr><td class="fw-semibold">${c.certificate_number}</td><td>${c.applicant_name}</td><td>${statusBadge(c.status)}</td><td>v${c.version_number}</td></tr>`)
    .join("");

  ctRenderPagination(document.getElementById("adminCertPagination"), filtered.length, adminCertPage, ADMIN_CERT_PAGE_SIZE, (p) => {
    adminCertPage = p;
    renderAllCertificatesTable();
  });
}

async function loadAllCertificates() {
  const tbody = document.getElementById("allCertificatesBody");
  try {
    allCertsAdmin = await ctFetch("/api/admin/certificates");
    adminCertPage = 1;
    renderAllCertificatesTable();
  } catch (err) {
    tbody.innerHTML = `<tr><td colspan="4" class="text-danger text-center">${err.message}</td></tr>`;
  }
}

function exportAllCertificatesCsv() {
  ctExportCsv("certitrust_all_certificates.csv", allCertsAdmin, [
    { key: "certificate_number", label: "Certificate Number" },
    { key: "applicant_name", label: "Applicant" },
    { key: "status", label: "Status" },
    { key: "version_number", label: "Version" },
  ]);
}

document.getElementById("userSearchInput")?.addEventListener("input", () => {
  userPage = 1;
  renderUsersTable();
});
document.getElementById("certAdminSearchInput")?.addEventListener("input", () => {
  adminCertPage = 1;
  renderAllCertificatesTable();
});

document.getElementById("userForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    full_name: document.getElementById("u_full_name").value.trim(),
    email: document.getElementById("u_email").value.trim(),
    password: document.getElementById("u_password").value,
    role: document.getElementById("u_role").value,
    department: document.getElementById("u_department").value.trim(),
  };
  try {
    await ctFetch("/api/admin/users", { method: "POST", body: JSON.stringify(payload) });
    ctToast("User created.", "success");
    bootstrap.Modal.getInstance(document.getElementById("userModal")).hide();
    e.target.reset();
    loadUsers();
  } catch (err) {
    ctToast(err.message, "danger");
  }
});

document.getElementById("certTypeForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = {
    name: document.getElementById("ct_name").value.trim(),
    code: document.getElementById("ct_code").value.trim(),
    department: document.getElementById("ct_department").value.trim(),
    validity_days: document.getElementById("ct_validity").value,
  };
  try {
    await ctFetch("/api/admin/certificate-types", { method: "POST", body: JSON.stringify(payload) });
    ctToast("Certificate type created.", "success");
    bootstrap.Modal.getInstance(document.getElementById("certTypeModal")).hide();
    e.target.reset();
    loadCertTypes();
  } catch (err) {
    ctToast(err.message, "danger");
  }
});

document.getElementById("deptForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const payload = { name: document.getElementById("d_name").value.trim(), code: document.getElementById("d_code").value.trim() };
  try {
    await ctFetch("/api/admin/departments", { method: "POST", body: JSON.stringify(payload) });
    ctToast("Department created.", "success");
    bootstrap.Modal.getInstance(document.getElementById("deptModal")).hide();
    e.target.reset();
    loadDepartments();
  } catch (err) {
    ctToast(err.message, "danger");
  }
});

loadStats();
loadUsers();
loadCertTypes();
loadDepartments();
loadAllCertificates();
