/**
 * Prime Gate Antigravity - System Dashboard Logic
 * Multi-tab Architecture with Tailwind CSS v4, Chart.js Token Telemetry, and WebSocket Streaming
 */

let currentTimeRange = "minute";
let tokenChart = null;
let liveSocket = null;
let reconnectTimer = null;
let currentTab = "dashboard";

// -------------------------------------------------------------
// Responsive Sidebar & Toast Notification Engine
// -------------------------------------------------------------

function toggleSidebar(open) {
  const sidebar = document.getElementById("mainSidebar");
  const backdrop = document.getElementById("sidebarBackdrop");
  if (!sidebar) return;

  if (open) {
    sidebar.classList.remove("-translate-x-full");
    if (backdrop) backdrop.classList.remove("hidden");
  } else {
    sidebar.classList.add("-translate-x-full");
    if (backdrop) backdrop.classList.add("hidden");
  }
}

/**
 * Modern In-App Toast Notification (replaces native alert)
 * @param {string} message - Message text
 * @param {'success'|'error'|'warning'|'info'|'critical'} type - Toast aesthetic type
 * @param {string|null} title - Optional title override
 * @param {number} duration - Auto-dismiss timeout in ms (default 3800ms)
 */
function showToast(message, type = "info", title = null, duration = 3800) {
  const container = document.getElementById("toastContainer");
  if (!container) return;

  const toast = document.createElement("div");
  const isCritical = type === "critical";
  const resolvedTitle = title || (isCritical ? "Critical Alert" : type === "success" ? "Success" : type === "error" ? "Failed" : type === "warning" ? "Warning" : "Information");

  let iconSvg = "";
  let themeClasses = "";
  let titleColor = "";

  if (isCritical) {
    themeClasses = "bg-[#2d0910]/95 border-rose-500/60 text-rose-50 shadow-2xl shadow-rose-950/60 ring-1 ring-rose-500/40";
    titleColor = "text-rose-400";
    iconSvg = `
      <div class="relative flex items-center justify-center shrink-0 w-4 h-4 mt-0.5">
        <span class="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-rose-400 opacity-75"></span>
        <span class="relative inline-flex rounded-full h-2 w-2 bg-rose-500"></span>
      </div>
    `;
  } else if (type === "success") {
    themeClasses = "bg-[#092218]/95 border-[#10b981]/40 text-[#ecfdf5] shadow-[#10b981]/10";
    titleColor = "text-[#10b981]";
    iconSvg = `<svg class="w-4 h-4 text-[#10b981] shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
  } else if (type === "error") {
    themeClasses = "bg-[#280c12]/95 border-rose-500/40 text-rose-50 shadow-rose-950/20";
    titleColor = "text-rose-400";
    iconSvg = `<svg class="w-4 h-4 text-rose-400 shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
  } else if (type === "warning") {
    themeClasses = "bg-[#251707]/95 border-[#f59e0b]/40 text-amber-50 shadow-amber-950/20";
    titleColor = "text-[#f59e0b]";
    iconSvg = `<svg class="w-4 h-4 text-[#f59e0b] shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`;
  } else {
    themeClasses = "bg-[#111927]/95 border-[#38bdf8]/40 text-sky-50 shadow-sky-950/20";
    titleColor = "text-[#38bdf8]";
    iconSvg = `<svg class="w-4 h-4 text-[#38bdf8] shrink-0 mt-0.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
  }

  toast.className = `toast-item flex items-start gap-3 p-3.5 rounded-xl border shadow-xl backdrop-blur-md pointer-events-auto transition-all duration-300 ${themeClasses}`;
  toast.innerHTML = `
    ${iconSvg}
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-1.5 flex-wrap">
        ${isCritical ? '<span class="text-[9px] font-mono-code font-bold uppercase tracking-wider px-1.5 py-0.5 rounded bg-rose-500/25 text-rose-300 border border-rose-500/40">[CRITICAL ALERT]</span>' : ''}
        <span class="text-xs font-semibold ${titleColor} tracking-wide">${resolvedTitle}</span>
      </div>
      <div class="text-[11px] text-[#d6d3d1] mt-1 leading-relaxed break-words font-mono-code">${message}</div>
    </div>
    <button class="text-[#a8a29e] hover:text-white transition p-0.5 rounded ml-1 shrink-0" onclick="this.parentElement.remove()" title="Close">
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
    </button>
  `;

  container.appendChild(toast);

  if (duration > 0) {
    setTimeout(() => {
      toast.style.opacity = "0";
      toast.style.transform = "translateY(10px) scale(0.96)";
      setTimeout(() => toast.remove(), 280);
    }, duration);
  }
}

/**
 * Reusable Confirmation Dialog (replaces native window.confirm)
 * @returns {Promise<boolean>}
 */
function showConfirmModal({
  title = "Confirm Action",
  message = "Are you sure you want to proceed with this action?",
  confirmText = "Continue",
  cancelText = "Cancel",
  type = "danger"
}) {
  return new Promise((resolve) => {
    const modal = document.getElementById("confirmModal");
    const titleEl = document.getElementById("confirmModalTitle");
    const msgEl = document.getElementById("confirmModalMessage");
    const okBtn = document.getElementById("confirmModalOkBtn");
    const cancelBtn = document.getElementById("confirmModalCancelBtn");
    const iconEl = document.getElementById("confirmModalIcon");

    if (!modal) {
      resolve(true);
      return;
    }


    titleEl.innerText = title;
    msgEl.innerText = message;
    okBtn.innerText = confirmText;
    cancelBtn.innerText = cancelText;

    if (type === "danger") {
      okBtn.className = "py-2 px-4 rounded-lg bg-rose-600 hover:bg-rose-700 text-white text-xs font-semibold shadow transition active:scale-95";
      iconEl.className = "w-10 h-10 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center mb-3";
      iconEl.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/></svg>`;
    } else if (type === "warning") {
      okBtn.className = "py-2 px-4 rounded-lg bg-amber-600 hover:bg-amber-700 text-white text-xs font-semibold shadow transition active:scale-95";
      iconEl.className = "w-10 h-10 rounded-full bg-amber-500/20 text-amber-400 flex items-center justify-center mb-3";
      iconEl.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"/></svg>`;
    } else {
      okBtn.className = "py-2 px-4 rounded-lg bg-[#d97706] hover:bg-[#b45309] text-white text-xs font-semibold shadow transition active:scale-95";
      iconEl.className = "w-10 h-10 rounded-full bg-[#d97706]/20 text-[#f59e0b] flex items-center justify-center mb-3";
      iconEl.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    }

    modal.style.display = "flex";

    const close = (val) => {
      modal.style.display = "none";
      okBtn.onclick = null;
      cancelBtn.onclick = null;
      resolve(val);
    };

    okBtn.onclick = () => close(true);
    cancelBtn.onclick = () => close(false);
  });
}

/**
 * Reusable Information Modal (replaces native window.alert for rich details)
 * @returns {Promise<void>}
 */
function showAlertModal({
  title = "Information",
  message = "",
  type = "info",
  okText = "Close"
}) {
  return new Promise((resolve) => {
    const modal = document.getElementById("alertModal");
    const titleEl = document.getElementById("alertModalTitle");
    const msgEl = document.getElementById("alertModalMessage");
    const okBtn = document.getElementById("alertModalOkBtn");
    const iconEl = document.getElementById("alertModalIcon");

    if (!modal) {
      showToast(message, type, title);
      resolve();
      return;
    }

    titleEl.innerText = title;
    msgEl.innerText = message;
    okBtn.innerText = okText;

    if (type === "error") {
      iconEl.className = "w-10 h-10 rounded-full bg-rose-500/20 text-rose-400 flex items-center justify-center mb-3";
      iconEl.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    } else if (type === "success") {
      iconEl.className = "w-10 h-10 rounded-full bg-emerald-500/20 text-emerald-400 flex items-center justify-center mb-3";
      iconEl.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    } else {
      iconEl.className = "w-10 h-10 rounded-full bg-[#d97706]/20 text-[#f59e0b] flex items-center justify-center mb-3";
      iconEl.innerHTML = `<svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>`;
    }

    modal.style.display = "flex";

    okBtn.onclick = () => {
      modal.style.display = "none";
      okBtn.onclick = null;
      resolve();
    };
  });
}

// -------------------------------------------------------------
// Tab Navigation Routing
// -------------------------------------------------------------

function switchTab(tabId) {
  currentTab = tabId;

  // Auto close mobile drawer if open
  toggleSidebar(false);

  // Update nav buttons
  document.querySelectorAll(".nav-link").forEach(btn => {
    if (btn.getAttribute("data-tab") === tabId) {
      btn.classList.add("active");
    } else {
      btn.classList.remove("active");
    }
  });

  // Toggle content panels
  document.querySelectorAll(".tab-content").forEach(panel => {
    panel.style.display = "none";
  });
  const activePanel = document.getElementById(`tab-${tabId}`);
  if (activePanel) {
    activePanel.style.display = "flex";
  }

  // Action on tab activation
  if (tabId === "dashboard") {
    fetchTokenMetrics();
    if (tokenChart) tokenChart.resize();
  } else if (tabId === "accounts") {
    fetchAccounts();
    fetchStatus();
  } else if (tabId === "sandbox") {
    fetchStatus();
  } else if (tabId === "sentinel") {
    fetchDBStatus();
  }
}


// -------------------------------------------------------------
// Token Telemetry & Chart.js Bar Chart
// -------------------------------------------------------------

function initTokenChart() {
  const ctx = document.getElementById("tokenBarChart");
  if (!ctx) return;

  tokenChart = new Chart(ctx, {
    type: "bar",
    data: {
      labels: [],
      datasets: [
        {
          label: "Prompt Tokens",
          data: [],
          backgroundColor: "#b45309",
          borderRadius: 3,
          barPercentage: 0.7,
          stack: "tokens"
        },
        {
          label: "Reasoning Tokens",
          data: [],
          backgroundColor: "#d97706",
          borderRadius: 3,
          barPercentage: 0.7,
          stack: "tokens"
        },
        {
          label: "Completion Tokens",
          data: [],
          backgroundColor: "#f59e0b",
          borderRadius: 3,
          barPercentage: 0.7,
          stack: "tokens"
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      scales: {
        x: {
          stacked: true,
          grid: { color: "rgba(168, 162, 158, 0.06)" },
          ticks: {
            color: "#78716c",
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            maxRotation: 0,
            autoSkip: true,
            maxTicksLimit: 12
          }
        },
        y: {
          stacked: true,
          grid: { color: "rgba(168, 162, 158, 0.08)" },
          ticks: {
            color: "#78716c",
            font: { family: "'JetBrains Mono', monospace", size: 10 },
            precision: 0
          }
        }
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: "#1b1613",
          titleColor: "#f5f5f4",
          bodyColor: "#d6d3d1",
          borderColor: "rgba(217, 119, 6, 0.4)",
          borderWidth: 1,
          padding: 10,
          titleFont: { family: "'JetBrains Mono', monospace", size: 11 },
          bodyFont: { family: "'JetBrains Mono', monospace", size: 11 },
          callbacks: {
            footer: (items) => {
              const total = items.reduce((acc, curr) => acc + curr.raw, 0);
              return `Total Volume: ${total} tokens`;
            }
          }
        }
      }
    }
  });
}

function changeTimeRange(range) {
  currentTimeRange = range;
  document.querySelectorAll(".time-pill").forEach(pill => pill.classList.remove("active"));
  const activePill = document.getElementById(`pill-${range}`);
  if (activePill) activePill.classList.add("active");
  fetchTokenMetrics();
}

async function fetchTokenMetrics() {
  try {
    const res = await fetch(`/api/metrics/tokens?range=${currentTimeRange}`);
    if (!res.ok) return;
    const data = await res.json();

    const summary = data.summary || {};
    const chart = data.chart_data || {};

    // Update KPI metrics
    document.getElementById("kpiTps").innerText = (summary.current_tokens_per_sec || 0).toFixed(1);
    document.getElementById("kpiTokensToday").innerText = (summary.tokens_today || 0).toLocaleString();
    document.getElementById("kpiLatency").innerText = Math.round(summary.avg_latency_ms || 0);
    document.getElementById("kpiTotalRequests").innerText = (summary.total_requests_all_time || 0).toLocaleString();
    
    document.getElementById("kpiTokensTodayBreakdown").innerText = 
      `Prompt: ${(summary.total_prompt_tokens || 0).toLocaleString()} | Comp: ${(summary.total_completion_tokens || 0).toLocaleString()} | Think: ${(summary.total_reasoning_tokens || 0).toLocaleString()}`;
    document.getElementById("kpiTotalTokensAllTime").innerText = 
      `Cumulative: ${(summary.total_tokens_all_time || 0).toLocaleString()} tokens`;

    // Update Bar Chart
    if (tokenChart) {
      tokenChart.data.labels = chart.labels || [];
      tokenChart.data.datasets[0].data = chart.prompt_tokens || [];
      tokenChart.data.datasets[1].data = chart.reasoning_tokens || [];
      tokenChart.data.datasets[2].data = chart.completion_tokens || [];
      tokenChart.update();
    }
  } catch (err) {
    console.warn("Could not fetch token metrics:", err);
  }
}

// -------------------------------------------------------------
// Status & Quota Radar Controller
// -------------------------------------------------------------

async function fetchStatus() {
  try {
    const res = await fetch("/api/status");
    if (!res.ok) return;
    const data = await res.json();

    const activeAcc = data.active_account || "No account connected";
    const tier = data.tier || "Unknown";

    // Update sidebar
    const sidebarEmail = document.getElementById("sidebarActiveEmail");
    if (sidebarEmail) sidebarEmail.innerText = activeAcc;

    const sidebarTier = document.getElementById("sidebarActiveTier");
    if (sidebarTier) {
      sidebarTier.innerText = tier.includes("Paid") ? "Paid Tier" : (tier.includes("Trial") ? "Trial Tier" : "Pro");
    }

    const sidebarSelect = document.getElementById("sidebarAccountSelect");
    if (sidebarSelect && data.active_account) {
      sidebarSelect.value = data.active_account;
    }

    // Update accounts tab identity
    const accEmail = document.getElementById("accActiveEmail");
    if (accEmail) accEmail.innerText = activeAcc;
    const accTier = document.getElementById("accTierBadge");
    if (accTier) accTier.innerText = tier;
    const accCount = document.getElementById("accCountBadge");
    if (accCount) accCount.innerText = `${data.total_accounts || 0} Accounts`;

    // Update Quota Bars on Dashboard and Accounts tab
    renderQuotaBars(data.quota || []);

    // Check onboarding modal
    if (!data.active_account && data.total_accounts === 0) {
      openAuthModal(false);
    }
  } catch (err) {
    console.warn("Status fetch failed:", err);
  }
}

function renderQuotaBars(quotas) {
  const dashContainer = document.getElementById("dashQuotaContainer");
  const accStack = document.getElementById("accQuotaStack");

  if (!quotas || quotas.length === 0) {
    const emptyHtml = `<div class="text-xs text-[#78716c] font-mono-code py-2">No quota telemetry available. Connect an Antigravity account.</div>`;
    if (dashContainer) dashContainer.innerHTML = emptyHtml;
    if (accStack) accStack.innerHTML = emptyHtml;
    return;
  }

  const html = quotas.map(q => {
    const pct = Math.max(0, Math.min(100, q.percentage));
    const isLow = pct < 20;
    const barColor = isLow ? "bg-rose-500" : (q.family.includes("claude") ? "bg-[#d97706]" : "bg-[#10b981]");
    const textBadge = isLow ? "text-rose-400" : (q.family.includes("claude") ? "text-[#f59e0b]" : "text-[#10b981]");

    return `
      <div class="p-3.5 bg-[#0f0d0b] border border-[#a8a29e]/10 rounded-xl hover:border-[#a8a29e]/20 transition">
        <div class="flex items-start justify-between text-xs mb-2 gap-3">
          <span class="font-medium text-white flex-1 leading-snug break-words">${q.label}</span>
          <span class="font-mono-code font-bold ${textBadge} px-2 py-0.5 rounded bg-white/5 border border-white/5 shrink-0">${pct}%</span>
        </div>
        <div class="w-full bg-white/5 h-2 rounded-full overflow-hidden border border-white/5 mb-2">
          <div class="${barColor} h-full progress-bar-fill rounded-full" style="width: ${pct}%;"></div>
        </div>
        <div class="flex flex-wrap items-center justify-between gap-1 text-[10px] text-[#78716c] font-mono-code">
          <span>Bucket: ${q.family}</span>
          <span>Reset: ${q.reset_time || "Active"}</span>
        </div>
      </div>
    `;
  }).join("");

  if (dashContainer) dashContainer.innerHTML = html;
  if (accStack) accStack.innerHTML = html;
}

// -------------------------------------------------------------
// Account Management & Connected Accounts
// -------------------------------------------------------------

async function fetchAccounts() {
  try {
    const res = await fetch("/api/accounts");
    if (!res.ok) return;
    const data = await res.json();
    const accounts = data.accounts || [];

    // Sync sidebar dropdown selector
    const sidebarSelect = document.getElementById("sidebarAccountSelect");
    if (sidebarSelect) {
      if (accounts.length === 0) {
        sidebarSelect.innerHTML = `
          <option value="" disabled selected>No accounts connected</option>
          <option value="__add__">+ Connect Account...</option>
        `;
      } else {
        let optHtml = "";
        accounts.forEach(a => {
          const tierTag = a.tier ? (a.tier.includes("Paid") ? "Paid" : "Trial") : "Pro";
          optHtml += `<option value="${a.email}" ${a.is_active ? "selected" : ""}>${a.email} (${tierTag})</option>`;
        });
        optHtml += `<option value="__add__">+ Connect Account...</option>`;
        sidebarSelect.innerHTML = optHtml;
      }
    }

    const deck = document.getElementById("accAccountsDeck");
    if (!deck) return;

    if (accounts.length === 0) {
      deck.innerHTML = `<div class="text-xs text-[#78716c] font-mono-code py-4 text-center">No accounts configured yet. Click "+ Connect Google Account" above.</div>`;
      return;
    }

    deck.innerHTML = accounts.map(a => `
      <div class="flex items-center justify-between p-3.5 bg-[#0f0d0b] border border-[#a8a29e]/10 rounded-lg hover:border-[#a8a29e]/20 transition">
        <div class="flex items-center gap-3">
          <div class="w-8 h-8 rounded-full bg-[#d97706]/15 border border-[#d97706]/30 flex items-center justify-center text-xs font-mono-code text-[#f59e0b] font-bold">
            ${(a.email || "G").charAt(0).toUpperCase()}
          </div>
          <div>
            <div class="flex items-center gap-2">
              <span class="text-xs font-medium text-white font-mono-code">${a.email}</span>
              ${a.is_active ? '<span class="text-[9px] px-1.5 py-0.2 bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/30 rounded font-mono-code font-bold">Active</span>' : ''}
            </div>
            <span class="text-[10px] text-[#78716c] font-mono-code block mt-0.5">${a.tier || "Standard Tier"} • Project: ${a.projectId || "default"}</span>
          </div>
        </div>
        <div class="flex items-center gap-2">
          ${!a.is_active ? `
          <button class="btn-secondary text-xs py-1 px-2.5 text-[#f59e0b] border-[#d97706]/30 hover:bg-[#d97706]/10 flex items-center gap-1.5 transition" onclick="switchSidebarAccount('${a.email}')" title="Set ${a.email} as active account">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
            Set Active
          </button>` : ''}
          <button class="btn-secondary text-xs py-1 px-2.5 text-rose-400 border-rose-900/40 hover:bg-rose-950/30 flex items-center gap-1.5 transition" onclick="removeAccount('${a.email}')" title="Delete account ${a.email}">
            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
            </svg>
            Delete
          </button>
        </div>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Could not fetch accounts:", err);
  }
}

function handleSidebarAccountSelect(val) {
  if (!val) return;
  if (val === "__add__") {
    // Revert selection back to active email
    const activeEl = document.getElementById("sidebarActiveEmail");
    const select = document.getElementById("sidebarAccountSelect");
    if (select && activeEl && activeEl.innerText && activeEl.innerText !== "Connecting...") {
      select.value = activeEl.innerText.trim();
    }
    openAuthModal(false);
    return;
  }
  switchSidebarAccount(val);
}

async function switchSidebarAccount(email) {
  if (!email) return;
  try {
    showToast(`Switching active account to ${email}...`, "info");
    const res = await fetch("/api/auth/switch", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      showToast(`Switched active account to ${email}`, "success");
      appendSentinelLog("Accounts", `Switched active account to ${email} (models: ${data.models_count}, quota: ${data.quota_count})`, "INFO");
      await fetchStatus();
      await fetchAccounts();
      await loadModelsList();
    } else {
      const err = extractErrorMessage(data, `Failed to switch to account ${email}`);
      showToast(err, "error");
      await fetchAccounts();
    }
  } catch (err) {
    showToast(`Failed to switch account: ${err.message}`, "error");
    await fetchAccounts();
  }
}

async function removeActiveAccount() {
  const activeEl = document.getElementById("accActiveEmail");
  const email = activeEl ? activeEl.innerText.trim() : "";
  if (!email || email === "—" || email === "No account connected") {
    showToast("No active account available to remove.", "warning");
    return;
  }
  await removeAccount(email);
}

async function removeAccount(email) {
  const confirmed = await showConfirmModal({
    title: "Remove Antigravity Account",
    message: `Are you sure you want to permanently remove account "${email}" from Prime Gate?`,
    confirmText: "Remove Account",
    cancelText: "Cancel",
    type: "danger"
  });
  if (!confirmed) return;

  try {
    const res = await fetch("/api/auth/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (data.success) {
      showToast(`Account "${email}" removed from database successfully.`, "success");
      appendSentinelLog("Accounts", `Account removed from binary database: ${email}`, "WARN");
      await fetchAccounts();
      await fetchStatus();
      if (data.total_accounts === 0) {
        openAuthModal(false);
      }
    } else {
      showToast("Failed to remove account: " + (data.error || "Unknown error"), "error");
    }
  } catch (err) {
    showToast("Failed to remove account: " + err.message, "error");
  }
}

async function clearAllAccounts() {
  const confirmed = await showConfirmModal({
    title: "Remove All Accounts",
    message: "Are you sure you want to remove ALL Google Antigravity accounts from Prime Gate? This will clear all stored credentials and quotas.",
    confirmText: "Remove All",
    cancelText: "Cancel",
    type: "danger"
  });
  if (!confirmed) return;

  try {
    const res = await fetch("/api/auth/clear", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      showToast("All accounts successfully cleared from compiled database.", "success");
      appendSentinelLog("Accounts", "All accounts cleared from binary database.", "WARN");
      await fetchAccounts();
      await fetchStatus();
      openAuthModal(false);
    }
  } catch (err) {
    showToast("Failed to clear accounts: " + err.message, "error");
  }
}


// -------------------------------------------------------------
// Google OAuth & OpenCode Import
// -------------------------------------------------------------

let currentAuthUrl = "";

function extractErrorMessage(data, fallback = "Unable to complete OAuth") {
  if (!data) return fallback;
  if (typeof data.error === "string" && data.error.trim()) return data.error;
  if (data.error && typeof data.error === "object") {
    if (data.error.message) return data.error.message;
    try { return JSON.stringify(data.error); } catch (e) {}
  }
  if (typeof data.detail === "string" && data.detail.trim()) return data.detail;
  if (Array.isArray(data.detail) && data.detail.length > 0) {
    return data.detail.map(d => d.msg || JSON.stringify(d)).join(", ");
  }
  if (typeof data.message === "string" && data.message.trim()) return data.message;
  return fallback;
}

function openAuthModal(canDismiss = true) {
  const modal = document.getElementById("authModal");
  const closeBtn = document.getElementById("authModalCloseBtn");
  const fallback = document.getElementById("authFallbackContainer");
  const notice = document.getElementById("authStatusNotice");
  if (!modal) return;
  modal.style.display = "flex";
  if (closeBtn) closeBtn.style.display = canDismiss ? "block" : "none";
  if (fallback) fallback.classList.add("hidden");
  if (notice) notice.innerText = "";
}

function closeAuthModal() {
  const modal = document.getElementById("authModal");
  const fallback = document.getElementById("authFallbackContainer");
  if (modal) modal.style.display = "none";
  if (fallback) fallback.classList.add("hidden");
}

async function triggerGoogleLogin() {
  const notice = document.getElementById("authStatusNotice");
  const btn = document.getElementById("googleLoginBtn");
  const fallback = document.getElementById("authFallbackContainer");
  const directLink = document.getElementById("authDirectLink");

  try {
    btn.disabled = true;
    notice.innerText = "⏳ Inisialisasi Google OAuth...";
    notice.style.color = "#f59e0b";

    // 1. Fetch official authorization URL first
    let authUrl = "";
    try {
      const urlRes = await fetch("/api/auth/url");
      if (urlRes.ok) {
        const urlData = await urlRes.json();
        authUrl = urlData.auth_url || "";
      }
    } catch (e) {
      console.warn("Could not prefetch auth url:", e);
    }

    if (authUrl) {
      currentAuthUrl = authUrl;
      if (directLink) directLink.href = authUrl;
      if (fallback) fallback.classList.remove("hidden");

      // Open tab directly from user interaction
      try {
        const popup = window.open(authUrl, "_blank");
        if (!popup || popup.closed || typeof popup.closed === "undefined") {
          notice.innerText = "⚠️ Browser popup blocked. Please click the manual link button below:";
          notice.style.color = "#f59e0b";
        } else {
          notice.innerText = "🚀 Google login tab opened! Please authorize in your browser...";
          notice.style.color = "#38bdf8";
        }
      } catch (err) {
        notice.innerText = "Please click 'Open Google Login Page' below:";
        notice.style.color = "#f59e0b";
      }
    } else {
      notice.innerText = "Waiting for browser authentication callback...";
      notice.style.color = "#f59e0b";
    }

    // 2. Trigger interactive listener and token exchange on backend
    const res = await fetch("/api/auth/login", { method: "POST" });
    const data = await res.json();

    if (data.success) {
      notice.innerText = `✓ Login successful as ${data.account}! Saving to binary database...`;
      notice.style.color = "#10b981";
      appendSentinelLog("Auth", `Google account successfully added: ${data.account}`, "INFO");
      setTimeout(async () => {
        closeAuthModal();
        await fetchAccounts();
        await fetchStatus();
        await loadModelsList();
      }, 1200);
    } else {
      const errMsg = extractErrorMessage(data, "Failed to complete Google OAuth");
      notice.innerText = `Login failed: ${errMsg}`;
      notice.style.color = "#f43f5e";
    }
  } catch (err) {
    notice.innerText = "Login request error: " + err.message;
    notice.style.color = "#f43f5e";
  } finally {
    btn.disabled = false;
  }
}

function copyAuthLink() {
  if (!currentAuthUrl) return;
  const btn = document.getElementById("copyAuthBtn");
  navigator.clipboard.writeText(currentAuthUrl).then(() => {
    if (btn) {
      const prev = btn.innerText;
      btn.innerText = "✓ Disalin!";
      btn.style.color = "#10b981";
      setTimeout(() => {
        btn.innerText = prev;
        btn.style.color = "";
      }, 2000);
    }
    showToast("Tautan otentikasi Google disalin ke clipboard!", "success");
  }).catch(e => {
    showAlertModal({
      title: "Google OAuth URL",
      message: currentAuthUrl,
      type: "info"
    });
  });
}


async function triggerImportOpenCode() {
  const notice = document.getElementById("authStatusNotice");
  const btn = document.getElementById("importAuthBtn");
  try {
    notice.innerText = "Scanning local OpenCode configuration...";
    notice.style.color = "#f59e0b";
    btn.disabled = true;

    const res = await fetch("/api/auth/import", { method: "POST" });
    const data = await res.json();
    if (data.success && data.imported > 0) {
      notice.innerText = `✓ Successfully imported ${data.imported} account(s)!`;
      notice.style.color = "#10b981";
      appendSentinelLog("Accounts", `Imported ${data.imported} accounts from OpenCode`, "INFO");
      setTimeout(async () => {
        closeAuthModal();
        await fetchAccounts();
        await fetchStatus();
        await loadModelsList();
      }, 1000);
    } else {
      const errMsg = extractErrorMessage(data, "No OpenCode credentials found. Use 'Sign in with Google' instead.");
      notice.innerText = errMsg;
      notice.style.color = "#f43f5e";
    }
  } catch (err) {
    notice.innerText = "Import error: " + err.message;
    notice.style.color = "#f43f5e";
  } finally {
    btn.disabled = false;
  }
}


// -------------------------------------------------------------
// Prompt Sandbox & Model Playground
// -------------------------------------------------------------

function setSamplePrompt(promptText) {
  const input = document.getElementById("sandboxPromptInput");
  if (input) {
    input.value = promptText;
    input.focus();
  }
}

async function syncModelsFromAntigravity() {
  try {
    showToast("Connecting to Google Antigravity to sync live models...", "info");
    const res = await fetch("/api/models/refresh", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      renderModels(data.models || []);
      renderQuotaBars(data.quota || []);
      showToast(`✓ Successfully loaded ${data.models_count} live models directly from Antigravity!`, "success");
    } else {
      showToast("Model synchronization failed: " + (data.error || "Unknown error"), "error");
    }
  } catch (err) {
    showToast("Synchronization request failed: " + err.message, "error");
  }
}

async function testPrompt() {
  const modelSelect = document.getElementById("sandboxModelSelect");
  const promptInput = document.getElementById("sandboxPromptInput");
  const sendBtn = document.getElementById("sandboxSendBtn");
  const outputArea = document.getElementById("sandboxOutputArea");
  const latencyBadge = document.getElementById("sandboxLatencyBadge");

  const model = modelSelect ? modelSelect.value : "gemini-3.8-flash";
  const prompt = promptInput ? promptInput.value.trim() : "";

  if (!prompt) {
    showToast("Please enter an instruction prompt or select an example above.", "warning");
    return;
  }


  sendBtn.disabled = true;
  outputArea.innerText = `Connecting to Google Antigravity [${model}]...\n`;
  latencyBadge.innerText = "";
  const startTime = Date.now();
  let isFirstChunk = true;

  try {
    const res = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": "Bearer prime-gate-proxy"
      },
      body: JSON.stringify({
        model: model,
        stream: true,
        messages: [{ role: "user", content: prompt }]
      })
    });

    if (!res.ok) {
      const errBody = await res.text();
      outputArea.innerText = `[Error ${res.status}]: ${errBody}`;
      return;
    }

    const reader = res.body.getReader();
    const decoder = new TextDecoder("utf-8");
    outputArea.innerText = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split("\n");

      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const jsonStr = line.slice(5).trim();
        if (jsonStr === "[DONE]") continue;

        try {
          const parsed = JSON.parse(jsonStr);
          const delta = parsed.choices?.[0]?.delta || {};

          if (isFirstChunk) {
            latencyBadge.innerText = `TTFT: ${Date.now() - startTime}ms`;
            isFirstChunk = false;
          }

          if (delta.reasoning_content) {
            outputArea.innerText += `[THINKING]: ${delta.reasoning_content}`;
          }
          if (delta.content) {
            outputArea.innerText += delta.content;
          }
        } catch (e) {
          // Chunk parse warning
        }
      }
    }
  } catch (err) {
    outputArea.innerText = `Connection failed: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
    // Auto refresh token metrics
    setTimeout(fetchTokenMetrics, 600);
  }
}

async function loadModelsList() {
  try {
    const res = await fetch("/v1/models");
    if (!res.ok) return;
    const data = await res.json();
    const models = data.data || [];
    renderModels(models);
  } catch (err) {
    console.warn("Could not load models:", err);
  }
}

function renderModels(models) {
  const countBadge = document.getElementById("sandboxModelCount");
  const grid = document.getElementById("sandboxModelsGrid");
  const select = document.getElementById("sandboxModelSelect");

  if (countBadge) countBadge.innerText = `${models.length} Models`;

  if (select && models.length > 0) {
    const curVal = select.value;
    select.innerHTML = models.map(m => `
      <option value="${m.id}" ${m.id === curVal ? "selected" : ""}>
        ${m.name || m.id}
      </option>
    `).join("");
  }

  if (grid) {
    grid.innerHTML = models.map(m => `
      <div class="p-3 bg-[#0f0d0b] border border-[#a8a29e]/10 rounded-lg hover:border-[#d97706]/30 transition">
        <span class="text-xs font-mono-code font-semibold text-[#f59e0b] block truncate">${m.id}</span>
        <span class="text-[11px] text-[#a8a29e] block mt-0.5">${m.name || m.id}</span>
        <span class="text-[9px] text-[#78716c] font-mono-code block mt-1 uppercase">Provider: ${m.owned_by || "google-antigravity"}</span>
      </div>
    `).join("");
  }
}

// -------------------------------------------------------------
// Real-Time WebSocket Telemetry & Database Sentinel
// -------------------------------------------------------------

function initWebSocket() {
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;
  const sideWs = document.getElementById("sidebarWsStatus");

  try {
    liveSocket = new WebSocket(wsUrl);

    liveSocket.onopen = () => {
      if (sideWs) {
        sideWs.innerHTML = `<span class="w-2 h-2 rounded-full bg-[#10b981] animate-pulse"></span>Live`;
        sideWs.style.color = "#10b981";
      }
      appendSentinelLog("System", "WebSocket telemetry channel established to Prime Gate core.", "INFO");
    };

    liveSocket.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
      } catch (e) {
        console.warn("WS parse error:", e);
      }
    };

    liveSocket.onclose = () => {
      if (sideWs) {
        sideWs.innerHTML = `<span class="w-2 h-2 rounded-full bg-rose-500"></span>Offline`;
        sideWs.style.color = "#fb7185";
      }
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(initWebSocket, 3000);
    };

    liveSocket.onerror = () => {
      if (liveSocket) liveSocket.close();
    };
  } catch (err) {
    console.error("WS connect failed:", err);
  }
}

function handleWSMessage(msg) {
  if (msg.type === "INIT_STATE") {
    if (msg.db) updateDBUI(msg.db);
  } else if (msg.type === "DB_HEALTH") {
    updateDBMetrics(msg);
  } else if (msg.type === "DB_MUTATION") {
    fetchDBStatus();
    if (msg.key === "system:accounts") {
      fetchStatus();
      fetchAccounts();
    }
  } else if (msg.type === "ACCOUNT_CONNECTED") {
    appendSentinelLog("Auth", `Google account connected: ${msg.email}`, "INFO");
    closeAuthModal();
    fetchStatus();
    fetchAccounts();
    loadModelsList();
  } else if (msg.type === "ACCOUNT_SWITCHED") {
    appendSentinelLog("Auth", `Active account switched to: ${msg.email}`, "INFO");
    fetchStatus();
    fetchAccounts();
    loadModelsList();
  } else if (msg.type === "LOG_ENTRY") {
    appendSentinelLog(msg.logger, msg.message, msg.level, msg.is_corrupt_alert);
    if (msg.is_corrupt_alert) {
      showCorruptionAlert("Corruption Alert in Log Stream", msg.message);
    }
  } else if (msg.type === "DB_CORRUPTED") {
    showCorruptionAlert(msg.reason, `Key: ${msg.key} | ${JSON.stringify(msg.details)}`);
    appendSentinelLog("CRITICAL_WATCHDOG", `[DATABASE_CORRUPT] Key: ${msg.key} - ${msg.reason}`, "CRITICAL", true);
  }
}

function appendSentinelLog(logger, message, level = "INFO", isAlert = false) {
  const logArea = document.getElementById("sentinelLogsArea");
  if (!logArea) return;
  const timeStr = new Date().toLocaleTimeString();
  const alertTag = isAlert ? "🚨 " : "";
  const line = `[${timeStr}] [${level}] ${alertTag}${logger}: ${message}\n`;
  if (logArea.innerText === "Connecting to live WebSocket event bus...") {
    logArea.innerText = "";
  }
  logArea.innerText += line;
  const allLines = logArea.innerText.split("\n");
  if (allLines.length > 300) {
    logArea.innerText = allLines.slice(-300).join("\n");
  }
  logArea.scrollTop = logArea.scrollHeight;
}

function clearLiveLogs() {
  const logArea = document.getElementById("sentinelLogsArea");
  if (logArea) logArea.innerText = "";
}

function showCorruptionAlert(title, message) {
  const healthBadge = document.getElementById("sentinelHealthBadge");
  if (healthBadge) {
    healthBadge.innerText = "CORRUPTED";
    healthBadge.className = "px-3 py-1 rounded-full text-xs font-mono-code font-bold bg-rose-500/20 text-rose-300 border border-rose-500/50";
  }

  // Wrap critical alert cleanly using the toast notification system
  const cleanTitle = title || "Database Integrity Violation";
  const cleanMessage = message || "CRC32 Checksum mismatch detected in compiled binary block.";
  showToast(cleanMessage, "critical", cleanTitle, 8000);

  // Maintain compatibility with any legacy banner elements
  const banner = document.getElementById("dbCorruptionAlert");
  if (banner) banner.style.display = "none";
}

function dismissCorruptionAlert() {
  const banner = document.getElementById("dbCorruptionAlert");
  if (banner) banner.style.display = "none";
}

async function fetchDBStatus() {
  try {
    const res = await fetch("/api/db/status");
    if (!res.ok) return;
    const data = await res.json();
    updateDBUI(data);
  } catch (err) {
    console.warn("Could not fetch DB status:", err);
  }
}

function updateDBUI(st) {
  const engineEl = document.getElementById("sentinelEngineText");
  const recordsEl = document.getElementById("sentinelRecordsText");
  const sizeEl = document.getElementById("sentinelSizeText");
  const healthBadge = document.getElementById("sentinelHealthBadge");

  if (engineEl) engineEl.innerText = st.engine || "Compiled C (SQLite WAL)";
  if (recordsEl) recordsEl.innerText = `${st.records_count || 0} Binary Records`;
  if (sizeEl) sizeEl.innerText = `${Math.round((st.size_bytes || 0) / 1024 * 10) / 10} KB`;
  if (healthBadge && healthBadge.innerText !== "CORRUPTED") {
    healthBadge.innerText = "Optimal";
    healthBadge.className = "px-3 py-1 rounded-full text-xs font-mono-code font-bold bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/30";
  }
}

function updateDBMetrics(metrics) {
  const recordsEl = document.getElementById("sentinelRecordsText");
  const sizeEl = document.getElementById("sentinelSizeText");
  const healthBadge = document.getElementById("sentinelHealthBadge");

  if (recordsEl) recordsEl.innerText = `${metrics.record_count || 0} Binary Records`;
  if (sizeEl) sizeEl.innerText = `${Math.round((metrics.size_bytes || 0) / 1024 * 10) / 10} KB`;
  if (healthBadge) {
    if (metrics.integrity_ok) {
      healthBadge.innerText = "Optimal";
      healthBadge.className = "px-3 py-1 rounded-full text-xs font-mono-code font-bold bg-[#10b981]/15 text-[#10b981] border border-[#10b981]/30";
    } else {
      healthBadge.innerText = "CORRUPTED";
      healthBadge.className = "px-3 py-1 rounded-full text-xs font-mono-code font-bold bg-rose-500/20 text-rose-300 border border-rose-500/50";
    }
  }
}

async function auditDatabase() {
  try {
    appendSentinelLog("Sentinel", "Executing SQLite B-Tree and CRC32 checksum audit...", "INFO");
    showToast("Menjalankan audit integritas database CRC32 & B-Tree...", "info");
    const res = await fetch("/api/db/check", { method: "POST" });
    const data = await res.json();
    if (data.healthy) {
      appendSentinelLog("Sentinel", `Audit passed: ${data.records_scanned} records verified, zero corruptions.`, "INFO");
      dismissCorruptionAlert();
      fetchDBStatus();
      showToast(`✓ Audit completed: ${data.records_scanned} blocks 100% HEALTHY!`, "success");
      showAlertModal({
        title: "✓ Database Audit Report",
        message: `Status: 100% HEALTHY\nVerified Records: ${data.records_scanned} blocks\nCRC32 Checksums: Valid & Synchronized\nEngine: Compiled C (SQLite WAL Mode)`,
        type: "success"
      });
    } else {
      showCorruptionAlert("Corruption Detected in Audit", JSON.stringify(data.corruptions));
      showToast(`🚨 Audit failed: ${data.corruptions_count} block(s) detected as corrupted!`, "error");
      showAlertModal({
        title: "🚨 Database Audit Failed!",
        message: `Found ${data.corruptions_count} corrupted block(s) in database!\n\nDetails:\n${JSON.stringify(data.corruptions, null, 2)}`,
        type: "error"
      });
    }
  } catch (err) {
    showToast("Failed to execute database audit: " + err.message, "error");
  }
}

async function testDatabaseCorruption() {
  const confirmed = await showConfirmModal({
    title: "Simulate Binary Database Corruption",
    message: "Inject simulated bit corruption into a compiled database block to test the Sentinel Watchdog detection and real-time alerts?",
    confirmText: "Inject Simulation",
    cancelText: "Cancel",
    type: "warning"
  });
  if (!confirmed) return;

  try {
    appendSentinelLog("Simulator", "Injecting simulated binary corruption into 'system:test_block'...", "WARN");
    const res = await fetch("/api/db/test-corrupt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "system:test_block" })
    });
    const data = await res.json();
    appendSentinelLog("Simulator", data.message, "WARN");
    showToast("Simulated bit corruption injected successfully!", "warning");
  } catch (err) {
    showToast("Failed to trigger simulation: " + err.message, "error");
  }
}

function copyEndpoint() {
  const codeEl = document.getElementById("dashEndpointCode");
  const code = codeEl ? codeEl.innerText.trim() : "http://127.0.0.1:52111/v1";
  navigator.clipboard.writeText(code).then(() => {
    showToast("Gateway endpoint copied to clipboard: " + code, "success");
  });
}


function copyDocSnippet(elementId, btnElement) {
  const el = document.getElementById(elementId);
  if (!el) return;
  const text = el.innerText || el.textContent;
  navigator.clipboard.writeText(text).then(() => {
    const originalHtml = btnElement.innerHTML;
    btnElement.innerHTML = `
      <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
      </svg>
      <span class="text-emerald-400 font-semibold">Copied!</span>
    `;
    setTimeout(() => {
      btnElement.innerHTML = originalHtml;
    }, 2000);
  }).catch(err => {
    console.error("Failed to copy snippet:", err);
  });
}

// -------------------------------------------------------------
// App Initialization
// -------------------------------------------------------------

window.addEventListener("DOMContentLoaded", () => {
  initTokenChart();
  fetchStatus();
  fetchTokenMetrics();
  loadModelsList();
  fetchDBStatus();
  initWebSocket();

  // Polling intervals
  setInterval(() => {
    if (currentTab === "dashboard") {
      fetchTokenMetrics();
    }
  }, 3000);

  setInterval(fetchStatus, 10000);
});
