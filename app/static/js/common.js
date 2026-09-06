function ctToast(message, type = "success") {
  const container = document.getElementById("ctToastContainer");
  if (!container) return alert(message);
  const id = "toast-" + Date.now();
  const bg = { success: "success", danger: "danger", warning: "warning", info: "info" }[type] || "secondary";
  const html = `
    <div id="${id}" class="toast align-items-center text-bg-${bg} border-0" role="alert">
      <div class="d-flex">
        <div class="toast-body">${message}</div>
        <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
      </div>
    </div>`;
  container.insertAdjacentHTML("beforeend", html);
  const toastEl = document.getElementById(id);
  const toast = new bootstrap.Toast(toastEl, { delay: 4000 });
  toast.show();
  toastEl.addEventListener("hidden.bs.toast", () => toastEl.remove());
}

async function ctFetch(url, options = {}) {
  options.headers = Object.assign({ "Content-Type": "application/json" }, options.headers || {});
  const res = await fetch(url, options);
  let data = {};
  try {
    data = await res.json();
  } catch (e) {
    data = {};
  }
  if (!res.ok) {
    throw new Error(data.error || "Something went wrong. Please try again.");
  }
  return data;
}

function ctLogout() {
  ctFetch("/api/auth/logout", { method: "POST" })
    .then(() => (window.location.href = "/"))
    .catch(() => (window.location.href = "/"));
}

function ctStatusBadgeClass(status) {
  const map = {
    ACTIVE: "badge-active",
    REVOKED: "badge-revoked",
    EXPIRED: "badge-expired",
    SUPERSEDED: "badge-verified-reissue",
    SUBMITTED: "badge-submitted",
    UNDER_REVIEW: "badge-submitted",
    APPROVED: "badge-approved",
    REJECTED: "badge-rejected",
    ISSUED: "badge-issued",
    VERIFIED_ORIGINAL: "badge-verified-original",
    VERIFIED_OFFICIAL_REISSUE: "badge-verified-reissue",
    TAMPERED_MODIFIED: "badge-tampered",
    FORGED_INVALID: "badge-forged",
    NOT_FOUND: "badge-not-found",
    PENDING_VERIFICATION: "badge-pending",
  };
  return map[status] || "badge-not-found";
}

function ctEmptyState(message, icon = "📭") {
  return `<div class="ct-empty-state"><div class="icon">${icon}</div><p class="mb-0">${message}</p></div>`;
}

/* ------------------------------------------------------------------ */
/* Dark / light theme toggle                                          */
/* ------------------------------------------------------------------ */
(function initTheme() {
  const saved = localStorage.getItem("ct-theme") || "light";
  document.documentElement.setAttribute("data-theme", saved);
})();

function ctToggleTheme() {
  const current = document.documentElement.getAttribute("data-theme") || "light";
  const next = current === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("ct-theme", next);
  const btn = document.getElementById("themeToggleBtn");
  if (btn) btn.textContent = next === "dark" ? "☀️" : "🌙";
}

document.addEventListener("DOMContentLoaded", () => {
  const btn = document.getElementById("themeToggleBtn");
  if (btn) {
    const current = document.documentElement.getAttribute("data-theme") || "light";
    btn.textContent = current === "dark" ? "☀️" : "🌙";
  }
});

/* ------------------------------------------------------------------ */
/* Notification bell (polling dropdown)                               */
/* ------------------------------------------------------------------ */
async function ctLoadNotifBell() {
  const bellBtn = document.getElementById("notifBellBtn");
  const dropdown = document.getElementById("notifDropdown");
  if (!bellBtn || !dropdown) return;
  try {
    const items = await ctFetch("/api/notifications");
    const unread = items.filter((n) => !n.is_read).length;
    bellBtn.classList.toggle("has-unread", unread > 0);
    if (items.length === 0) {
      dropdown.innerHTML = `<div class="text-center text-muted small py-3">No notifications yet.</div>`;
      return;
    }
    dropdown.innerHTML = items
      .slice(0, 8)
      .map(
        (n) => `
      <div class="notif-item">
        <div class="title">${n.title}</div>
        <div class="msg">${n.message || ""}</div>
        <div class="time">${n.created_at}</div>
      </div>`
      )
      .join("");
  } catch (err) {
    /* silent fail - bell is a nice-to-have, not critical path */
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const bellBtn = document.getElementById("notifBellBtn");
  const dropdown = document.getElementById("notifDropdown");
  if (!bellBtn || !dropdown) return;

  ctLoadNotifBell();
  setInterval(ctLoadNotifBell, 20000);

  bellBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    dropdown.classList.toggle("show");
  });
  document.addEventListener("click", (e) => {
    if (!dropdown.contains(e.target) && e.target !== bellBtn) {
      dropdown.classList.remove("show");
    }
  });
});

/* ------------------------------------------------------------------ */
/* Lightweight client-side search + pagination helper for tables       */
/* ------------------------------------------------------------------ */
function ctPaginate(items, page, pageSize) {
  const start = (page - 1) * pageSize;
  return items.slice(start, start + pageSize);
}

function ctRenderPagination(containerEl, totalItems, page, pageSize, onPageChange) {
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));
  if (totalPages <= 1) {
    containerEl.innerHTML = "";
    return;
  }
  containerEl.innerHTML = "";
  const prev = document.createElement("button");
  prev.textContent = "‹ Prev";
  prev.disabled = page === 1;
  prev.onclick = () => onPageChange(page - 1);
  containerEl.appendChild(prev);

  for (let p = 1; p <= totalPages; p++) {
    if (totalPages > 7 && p !== 1 && p !== totalPages && Math.abs(p - page) > 1) {
      if (p === 2 || p === totalPages - 1) {
        const dots = document.createElement("span");
        dots.textContent = "…";
        dots.className = "px-1 text-muted";
        containerEl.appendChild(dots);
      }
      continue;
    }
    const btn = document.createElement("button");
    btn.textContent = p;
    if (p === page) btn.classList.add("active");
    btn.onclick = () => onPageChange(p);
    containerEl.appendChild(btn);
  }

  const next = document.createElement("button");
  next.textContent = "Next ›";
  next.disabled = page === totalPages;
  next.onclick = () => onPageChange(page + 1);
  containerEl.appendChild(next);
}

/* ------------------------------------------------------------------ */
/* CSV export helper                                                   */
/* ------------------------------------------------------------------ */
function ctExportCsv(filename, rows, columns) {
  if (!rows || rows.length === 0) {
    ctToast("Nothing to export yet.", "warning");
    return;
  }
  const header = columns.map((c) => `"${c.label}"`).join(",");
  const lines = rows.map((row) =>
    columns
      .map((c) => {
        const val = row[c.key] === null || row[c.key] === undefined ? "" : String(row[c.key]);
        return `"${val.replace(/"/g, '""')}"`;
      })
      .join(",")
  );
  const csv = [header, ...lines].join("\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
  ctToast("Export downloaded.", "success");
}
