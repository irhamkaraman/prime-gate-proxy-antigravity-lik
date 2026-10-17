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
// Tab Navigation Routing
// -------------------------------------------------------------

function switchTab(tabId) {
  currentTab = tabId;

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
    document.getElementById("sidebarActiveEmail").innerText = activeAcc;

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
      <div class="p-3 bg-[#0f0d0b] border border-[#a8a29e]/10 rounded-lg">
        <div class="flex items-center justify-between text-xs mb-1.5">
          <span class="font-medium text-white truncate max-w-[280px]">${q.label}</span>
          <span class="font-mono-code font-bold ${textBadge}">${pct}%</span>
        </div>
        <div class="w-full bg-white/5 h-2 rounded-full overflow-hidden border border-white/5">
          <div class="${barColor} h-full progress-bar-fill rounded-full" style="width: ${pct}%;"></div>
        </div>
        <div class="flex items-center justify-between text-[10px] text-[#78716c] font-mono-code mt-1.5">
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
        <button class="btn-secondary text-xs py-1 px-2.5 text-rose-400 border-rose-900/40 hover:bg-rose-950/30" onclick="removeAccount('${a.email}')">
          Disconnect
        </button>
      </div>
    `).join("");
  } catch (err) {
    console.warn("Could not fetch accounts:", err);
  }
}

async function removeAccount(email) {
  if (!confirm(`Are you sure you want to disconnect ${email}?`)) return;
  try {
    const res = await fetch("/api/auth/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (data.success) {
      await fetchAccounts();
      await fetchStatus();
    }
  } catch (err) {
    alert("Failed to remove account: " + err.message);
  }
}

async function clearAllAccounts() {
  if (!confirm("Remove ALL configured Google Antigravity accounts from Prime Gate?")) return;
  try {
    const res = await fetch("/api/auth/clear", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      await fetchAccounts();
      await fetchStatus();
      openAuthModal(false);
    }
  } catch (err) {
    alert("Failed to clear accounts: " + err.message);
  }
}

// -------------------------------------------------------------
// Google OAuth & OpenCode Import
// -------------------------------------------------------------

function openAuthModal(canDismiss = true) {
  const modal = document.getElementById("authModal");
  const closeBtn = document.getElementById("authModalCloseBtn");
  if (!modal) return;
  modal.style.display = "flex";
  if (closeBtn) closeBtn.style.display = canDismiss ? "block" : "none";
}

function closeAuthModal() {
  const modal = document.getElementById("authModal");
  if (modal) modal.style.display = "none";
}

async function triggerGoogleLogin() {
  const notice = document.getElementById("authStatusNotice");
  const btn = document.getElementById("googleLoginBtn");
  try {
    notice.innerText = "Launching browser for Google OAuth sign-in... Please approve.";
    notice.style.color = "#f59e0b";
    btn.disabled = true;

    const res = await fetch("/api/auth/login", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      notice.innerText = `✓ Authenticated as ${data.account}! Loading dashboard...`;
      notice.style.color = "#10b981";
      setTimeout(async () => {
        closeAuthModal();
        await fetchAccounts();
        await fetchStatus();
      }, 1000);
    } else {
      notice.innerText = `Login failed: ${data.error || "Unable to complete OAuth"}`;
      notice.style.color = "#f43f5e";
    }
  } catch (err) {
    notice.innerText = "Login request error: " + err.message;
    notice.style.color = "#f43f5e";
  } finally {
    btn.disabled = false;
  }
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
      setTimeout(async () => {
        closeAuthModal();
        await fetchAccounts();
        await fetchStatus();
      }, 1000);
    } else {
      notice.innerText = "No OpenCode credentials found. Use 'Sign in with Google' instead.";
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
    const res = await fetch("/api/models/refresh", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      renderModels(data.models || []);
      renderQuotaBars(data.quota || []);
      alert(`✓ Successfully synced ${data.models_count} models directly from your Antigravity account!`);
    } else {
      alert("Model sync failed: " + (data.error || "Unknown error"));
    }
  } catch (err) {
    alert("Model sync request failed: " + err.message);
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
    alert("Please enter a test prompt or choose a sample prompt.");
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
  const banner = document.getElementById("dbCorruptionAlert");
  const titleEl = document.getElementById("alertTitle");
  const msgEl = document.getElementById("alertMessage");
  const healthBadge = document.getElementById("sentinelHealthBadge");
  if (!banner) return;

  if (titleEl) titleEl.innerText = `🚨 Critical Database Alert: ${title}`;
  if (msgEl) msgEl.innerText = message;
  if (healthBadge) {
    healthBadge.innerText = "CORRUPTED";
    healthBadge.className = "px-3 py-1 rounded-full text-xs font-mono-code font-bold bg-rose-500/20 text-rose-300 border border-rose-500/50";
  }
  banner.style.display = "flex";
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
    const res = await fetch("/api/db/check", { method: "POST" });
    const data = await res.json();
    if (data.healthy) {
      alert(`✓ Database Audit Passed!\nScanned: ${data.records_scanned} binary records\nStatus: 100% HEALTHY`);
      appendSentinelLog("Sentinel", `Audit passed: ${data.records_scanned} records verified, zero corruptions.`, "INFO");
      dismissCorruptionAlert();
      fetchDBStatus();
    } else {
      showCorruptionAlert("Corruption Detected in Audit", JSON.stringify(data.corruptions));
      alert(`🚨 Database Audit Failed!\nFound ${data.corruptions_count} corrupted blocks!`);
    }
  } catch (err) {
    alert("Audit request failed: " + err.message);
  }
}

async function testDatabaseCorruption() {
  if (!confirm("Simulate binary bit tampering in the compiled database to test instant WebSocket alert and logging?")) return;

  try {
    appendSentinelLog("Simulator", "Injecting simulated binary corruption into 'system:test_block'...", "WARN");
    const res = await fetch("/api/db/test-corrupt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "system:test_block" })
    });
    const data = await res.json();
    appendSentinelLog("Simulator", data.message, "WARN");
  } catch (err) {
    alert("Failed to trigger simulation: " + err.message);
  }
}

function copyEndpoint() {
  const code = document.getElementById("dashEndpointCode").innerText;
  navigator.clipboard.writeText(code);
  alert("Endpoint copied to clipboard: " + code);
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
