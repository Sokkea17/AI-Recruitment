// Modern SaaS HR Dashboard Client Script with Day / Night Mode

document.addEventListener("DOMContentLoaded", () => {
  // 1. Theme Management (Day Mode / Night Mode)
  const themeToggleBtn = document.getElementById("themeToggleBtn");
  const themeModeLabel = document.getElementById("themeModeLabel");

  function applyTheme(theme) {
    document.documentElement.setAttribute("data-theme", theme);
    localStorage.setItem("theme", theme);
    if (themeModeLabel) {
      themeModeLabel.innerText = theme === "dark" ? "Night" : "Day";
    }
  }

  // Sync button label with initial theme
  const activeTheme = document.documentElement.getAttribute("data-theme") || localStorage.getItem("theme") || "dark";
  applyTheme(activeTheme);

  if (themeToggleBtn) {
    themeToggleBtn.addEventListener("click", () => {
      const current = document.documentElement.getAttribute("data-theme") || "dark";
      const nextTheme = current === "dark" ? "light" : "dark";
      applyTheme(nextTheme);
      showToast(`Switched to ${nextTheme === "dark" ? "Night" : "Day"} mode`, "info");
    });
  }

  // 2. Sidebar Collapse Management
  const sidebar = document.querySelector(".sidebar");
  const collapseBtn = document.querySelector(".sidebar-collapse-btn");

  if (sidebar && collapseBtn) {
    const isCollapsed = localStorage.getItem("saas_sidebar_collapsed") === "true";
    if (isCollapsed) {
      sidebar.classList.add("collapsed");
    }

    collapseBtn.addEventListener("click", () => {
      sidebar.classList.toggle("collapsed");
      localStorage.setItem("saas_sidebar_collapsed", sidebar.classList.contains("collapsed"));
    });
  }

  // 3. Global Modal Confirmation Logic
  window.openConfirmModal = function(title, message, confirmBtnText, onConfirm) {
    const overlay = document.getElementById("globalConfirmModal");
    if (!overlay) {
      if (confirm(message)) {
        onConfirm();
      }
      return;
    }

    document.getElementById("modalTitle").innerText = title;
    document.getElementById("modalMessage").innerText = message;
    const confirmBtn = document.getElementById("modalConfirmBtn");
    confirmBtn.innerText = confirmBtnText || "Confirm";

    if (confirmBtnText && (confirmBtnText.toLowerCase().includes("delete") || confirmBtnText.toLowerCase().includes("close") || confirmBtnText.toLowerCase().includes("cancel"))) {
      confirmBtn.style.backgroundColor = "var(--danger)";
      confirmBtn.style.borderColor = "var(--danger)";
      confirmBtn.style.color = "#ffffff";
    } else {
      confirmBtn.style.backgroundColor = "";
      confirmBtn.style.borderColor = "";
      confirmBtn.style.color = "";
    }

    const closeHandler = () => {
      overlay.classList.remove("active");
      confirmBtn.onclick = null;
    };

    document.getElementById("modalCancelBtn").onclick = closeHandler;
    confirmBtn.onclick = () => {
      closeHandler();
      onConfirm();
    };

    overlay.classList.add("active");
  };

  // 4. Toast Notifications
  window.showToast = function(message, type = "info") {
    const container = document.getElementById("toastContainer") || document.body;
    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${type === 'success' ? '✓' : type === 'error' ? '✕' : 'ℹ'}</span> <span>${message}</span>`;
    container.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transition = "opacity 0.3s ease";
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  };

  // 5. Quick Status Update Dropdowns
  document.querySelectorAll(".quick-status-select").forEach(select => {
    select.addEventListener("change", async (e) => {
      const appId = select.dataset.appId;
      const newStatus = select.value;
      const originalValue = select.dataset.current;

      try {
        const resp = await fetch(`/applications/${appId}/status`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Accept": "application/json"
          },
          body: JSON.stringify({ status: newStatus })
        });

        if (resp.ok) {
          select.dataset.current = newStatus;
          showToast(`Status updated to ${newStatus}`, "success");
        } else {
          select.value = originalValue;
          showToast("Failed to update status", "error");
        }
      } catch (err) {
        select.value = originalValue;
        showToast("Network error updating status", "error");
      }
    });
  });

  // 6. Regenerate AI Summary on Application Detail Page
  const regenBtn = document.getElementById("btnRegenerateAI");
  if (regenBtn) {
    regenBtn.addEventListener("click", async () => {
      const appId = regenBtn.dataset.appId;
      regenBtn.disabled = true;
      const originalText = regenBtn.innerHTML;
      regenBtn.innerHTML = `<span>⏳ Analyzing...</span>`;

      try {
        const resp = await fetch(`/applications/${appId}/regenerate-ai`, {
          method: "POST",
          headers: {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest"
          }
        });

        if (resp.ok) {
          const data = await resp.json();
          showToast("AI Summary regenerated successfully!", "success");
          setTimeout(() => window.location.reload(), 600);
        } else {
          showToast("Unable to regenerate AI Summary", "error");
          regenBtn.disabled = false;
          regenBtn.innerHTML = originalText;
        }
      } catch (err) {
        showToast("Error connecting to server", "error");
        regenBtn.disabled = false;
        regenBtn.innerHTML = originalText;
      }
    });
  }

  // 7. Interactive Timeline Tab Switching (7 Days vs 30 Days)
  const tab7d = document.getElementById("tabTimeline7d");
  const tab30d = document.getElementById("tabTimeline30d");
  const view7d = document.getElementById("viewTimeline7d");
  const view30d = document.getElementById("viewTimeline30d");

  if (tab7d && tab30d && view7d && view30d) {
    tab7d.addEventListener("click", () => {
      tab7d.classList.add("btn-primary");
      tab7d.classList.remove("btn-secondary");
      tab30d.classList.add("btn-secondary");
      tab30d.classList.remove("btn-primary");
      view7d.style.display = "flex";
      view30d.style.display = "none";
    });

    tab30d.addEventListener("click", () => {
      tab30d.classList.add("btn-primary");
      tab30d.classList.remove("btn-secondary");
      tab7d.classList.add("btn-secondary");
      tab7d.classList.remove("btn-primary");
      view7d.style.display = "none";
      view30d.style.display = "flex";
    });
  }
});
