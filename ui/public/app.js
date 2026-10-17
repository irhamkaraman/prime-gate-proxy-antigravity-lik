/**
 * Prime Gate Antigravity - System Dashboard Logic (Anthropic Theme)
 */

let isUserDismissedAuth = false;
let hasConfiguredAccount = false;

function openAuthModal(canDismiss = true) {
  const modal = document.getElementById("authModal");
  const closeBtn = document.getElementById("authModalCloseBtn");
  if (!modal) return;
  modal.style.display = "flex";
  if (closeBtn) {
    closeBtn.style.display = canDismiss ? "block" : "none";
  }
}

function closeAuthModal() {
  const modal = document.getElementById("authModal");
  if (!modal) return;
  modal.style.display = "none";
  isUserDismissedAuth = true;
}

async function triggerImportOpenCode() {
  const statusNotice = document.getElementById("authStatusNotice");
  const importBtn = document.getElementById("importAuthBtn");
  const googleBtn = document.getElementById("googleLoginBtn");

  try {
    statusNotice.innerText = "Scanning local OpenCode configuration...";
    statusNotice.style.color = "#f59e0b";
    importBtn.disabled = true;
    googleBtn.disabled = true;

    const res = await fetch("/api/auth/import", { method: "POST" });
    const data = await res.json();

    if (data.success && data.imported > 0) {
      statusNotice.innerText = `✓ Successfully imported ${data.imported} account(s)! Unlocking dashboard...`;
      statusNotice.style.color = "#10b981";
      isUserDismissedAuth = false;
      setTimeout(async () => {
        closeAuthModal();
        await fetchStatus();
      }, 1000);
    } else {
      statusNotice.innerText = "No OpenCode credentials found. Use 'Sign in with Google' instead.";
      statusNotice.style.color = "#f43f5e";
    }
  } catch (err) {
    statusNotice.innerText = `Import failed: ${err.message}`;
    statusNotice.style.color = "#f43f5e";
  } finally {
    importBtn.disabled = false;
    googleBtn.disabled = false;
  }
}

async function triggerGoogleLogin() {
  const statusNotice = document.getElementById("authStatusNotice");
  const importBtn = document.getElementById("importAuthBtn");
  const googleBtn = document.getElementById("googleLoginBtn");

  try {
    statusNotice.innerText = "Launching browser for Google OAuth sign-in... Please approve.";
    statusNotice.style.color = "#f59e0b";
    importBtn.disabled = true;
    googleBtn.disabled = true;

    const res = await fetch("/api/auth/login", { method: "POST" });
    const data = await res.json();

    if (data.success) {
      statusNotice.innerText = `✓ Authenticated as ${data.account}! Loading dashboard...`;
      statusNotice.style.color = "#10b981";
      isUserDismissedAuth = false;
      setTimeout(async () => {
        closeAuthModal();
        await fetchStatus();
      }, 1200);
    } else {
      statusNotice.innerText = `Login failed: ${data.error || "Unable to complete OAuth"}`;
      statusNotice.style.color = "#f43f5e";
    }
  } catch (err) {
    statusNotice.innerText = `Login request error: ${err.message}`;
    statusNotice.style.color = "#f43f5e";
  } finally {
    importBtn.disabled = false;
    googleBtn.disabled = false;
  }
}

async function fetchStatus() {
  const indicator = document.getElementById("statusIndicator");
  const statusText = document.getElementById("statusText");

  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("API unreachable");
    const data = await res.json();

    indicator.className = "status-pill online";
    statusText.innerText = "Connected & Active";

    hasConfiguredAccount = data.total_accounts > 0 && !!data.active_account;

    document.getElementById("accountTier").innerText = data.tier || "Active Plan";
    document.getElementById("accountEmail").innerText = data.active_account || "No Account Configured";
    document.getElementById("accountCount").innerText = `${data.total_accounts} Configured`;

    const uptimeMins = Math.floor(data.uptime / 60);
    const uptimeSecs = data.uptime % 60;
    document.getElementById("serverUptime").innerText = `${uptimeMins}m ${uptimeSecs}s`;

    // Onboarding check: If no account is configured, enforce the onboarding splash screen
    if (!hasConfiguredAccount) {
      openAuthModal(false); // Cannot dismiss if 0 accounts
    } else if (!isUserDismissedAuth) {
      // If accounts are configured and user did not manually open modal, ensure modal is closed
      const modal = document.getElementById("authModal");
      if (modal && modal.style.display !== "none" && !document.getElementById("authStatusNotice").innerText.includes("Launching")) {
        closeAuthModal();
      }
    }

    renderQuota(data.quota || []);
    fetchModels();
    fetchAccounts();
  } catch (err) {
    indicator.className = "status-pill offline";
    statusText.innerText = "Core API Offline";
    document.getElementById("quotaContainer").innerHTML = `
      <div class="empty-state" style="color: #f43f5e;">
        ⚠️ Python Core API is not detected on port 52111.<br>
        Please launch the service via <code>prime-gate daemon start</code> or <code>scripts\\start-all.bat</code>.
      </div>
    `;
  }
}

async function fetchAccounts() {
  const wrap = document.getElementById("accountsListWrap");
  const deck = document.getElementById("accountsDeck");
  if (!wrap || !deck) return;

  try {
    const res = await fetch("/api/accounts");
    if (!res.ok) return;
    const data = await res.json();
    const accounts = data.accounts || [];

    if (accounts.length === 0) {
      wrap.style.display = "none";
      return;
    }

    wrap.style.display = "block";
    deck.innerHTML = accounts.map(a => `
      <div class="account-item-row">
        <div class="account-item-meta">
          <div class="account-item-email">${a.email}</div>
          <div class="account-item-badge ${a.is_active ? 'active-id' : ''}">
            ${a.is_active ? '● Active Identity' : '○ Standby'} • ${a.tier}
          </div>
        </div>
        <button class="account-remove-btn" onclick="removeAccount('${a.email}')" title="Disconnect this account">Disconnect</button>
      </div>
    `).join("");
  } catch (e) {
    console.error("Error fetching accounts:", e);
  }
}

async function removeAccount(email) {
  if (!confirm(`Are you sure you want to disconnect ${email} from Prime Gate?`)) {
    return;
  }
  try {
    const res = await fetch("/api/auth/remove", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email })
    });
    const data = await res.json();
    if (data.success) {
      isUserDismissedAuth = false;
      await fetchStatus();
      alert(`✓ Account ${email} disconnected successfully.`);
    } else {
      alert("Failed to disconnect account: " + (data.detail || "Account not found"));
    }
  } catch (err) {
    alert("Request error: " + err.message);
  }
}

async function clearAllAccounts() {
  if (!confirm("Are you sure you want to remove ALL accounts from Prime Gate?\nThis will reset Prime Gate to the initial onboarding state.")) {
    return;
  }
  try {
    const res = await fetch("/api/auth/clear", { method: "POST" });
    const data = await res.json();
    if (data.success) {
      isUserDismissedAuth = false;
      await fetchStatus();
      alert("✓ All accounts have been disconnected from Prime Gate.");
    } else {
      alert("Failed to clear accounts.");
    }
  } catch (err) {
    alert("Request error: " + err.message);
  }
}

function renderQuota(quotaList) {
  const container = document.getElementById("quotaContainer");
  if (!quotaList || quotaList.length === 0) {
    container.innerHTML = '<div class="empty-state">No quota telemetry available for this account.</div>';
    return;
  }

  container.innerHTML = quotaList.map(item => {
    const pct = item.percentage;
    let color = "#10b981"; // Emerald green
    if (pct < 20) color = "#f43f5e"; // Rose
    else if (pct < 50) color = "#d97706"; // Warm Terracotta

    return `
      <div class="quota-node">
        <div class="quota-header-row">
          <span class="quota-title-text">${item.label}</span>
          <span class="quota-pct-text" style="color: ${color}">${pct}%</span>
        </div>
        <div class="quota-track">
          <div class="quota-progress-bar" style="width: ${pct}%; background: ${color};"></div>
        </div>
        <div class="quota-reset-stamp">Reset: ${item.reset_time}</div>
      </div>
    `;
  }).join("");
}

async function fetchModels() {
  try {
    const res = await fetch("/v1/models");
    if (!res.ok) return;
    const data = await res.json();
    const models = data.data || [];

    document.getElementById("modelCountBadge").innerText = `${models.length} Models`;

    const grid = document.getElementById("modelsGrid");
    grid.innerHTML = models.map(m => `
      <div class="catalog-card">
        <div class="catalog-model-id">${m.id}</div>
        <div class="catalog-provider">Provider: ${m.owned_by}</div>
      </div>
    `).join("");

    // Populate sandbox select box
    const select = document.getElementById("modelSelect");
    const currentVal = select.value;
    select.innerHTML = models.map(m => `
      <option value="${m.id}" ${m.id === currentVal ? "selected" : ""}>${m.id}</option>
    `).join("");
  } catch (e) {
    console.error("Error fetching models:", e);
  }
}

async function syncModelsFromAntigravity() {
  const badge = document.getElementById("modelCountBadge");
  const originalText = badge.innerText;
  try {
    badge.innerText = "Syncing...";
    const res = await fetch("/api/models/refresh", { method: "POST" });
    if (!res.ok) throw new Error("Sync request failed");
    const data = await res.json();
    if (data.success) {
      await fetchStatus();
      alert(`✓ Synced ${data.models_count} live models directly from Google Antigravity (${data.account})!`);
    } else {
      alert("Sync failed: " + (data.error || "Unknown error"));
    }
  } catch (err) {
    alert("Sync error: " + err.message);
  } finally {
    await fetchModels();
  }
}

async function testPrompt() {
  const promptInput = document.getElementById("promptInput");
  const modelSelect = document.getElementById("modelSelect");
  const outputArea = document.getElementById("outputArea");
  const sendBtn = document.getElementById("sendBtn");
  const latencyBadge = document.getElementById("latencyBadge");

  const prompt = promptInput.value.trim();
  if (!prompt) {
    alert("Please enter a prompt or instruction first.");
    return;
  }

  const model = modelSelect.value;
  outputArea.innerText = "Connecting to Google Antigravity upstream...";
  latencyBadge.innerText = "";
  sendBtn.disabled = true;

  const startTime = Date.now();

  try {
    const response = await fetch("/v1/chat/completions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model: model,
        stream: true,
        messages: [{ role: "user", content: prompt }]
      })
    });

    if (!response.ok) {
      const errText = await response.text();
      outputArea.innerText = `Upstream Error (${response.status}):\n${errText}`;
      sendBtn.disabled = false;
      return;
    }

    outputArea.innerText = "";
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let isFirstChunk = true;

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
          console.warn("SSE chunk parse warning:", e);
        }
      }
    }
  } catch (err) {
    outputArea.innerText = `Network connection failed: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
  }
}

function copyEndpoint() {
  const code = document.getElementById("endpointCode").innerText;
  navigator.clipboard.writeText(code);
  alert("Endpoint copied to clipboard: " + code);
}

// -------------------------------------------------------------
// Real-Time WebSocket Telemetry & Database Sentinel Client
// -------------------------------------------------------------

let liveSocket = null;
let reconnectTimer = null;

function initWebSocket() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  // Use current host (works through Node proxy or direct FastAPI server)
  const wsUrl = `${protocol}//${window.location.host}/ws/live`;
  const badge = document.getElementById("wsIndicatorBadge");

  try {
    liveSocket = new WebSocket(wsUrl);

    liveSocket.onopen = () => {
      if (badge) {
        badge.innerText = "● WebSocket Connected";
        badge.style.background = "rgba(16, 185, 129, 0.15)";
        badge.style.color = "#10b981";
        badge.style.borderColor = "rgba(16, 185, 129, 0.3)";
      }
      appendLog("System", "WebSocket telemetry stream active. Connected to Prime Gate core.", "INFO");
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
      if (badge) {
        badge.innerText = "○ Disconnected (Reconnecting...)";
        badge.style.background = "rgba(244, 63, 94, 0.15)";
        badge.style.color = "#fb7185";
        badge.style.borderColor = "rgba(244, 63, 94, 0.3)";
      }
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(initWebSocket, 3000);
    };

    liveSocket.onerror = () => {
      if (liveSocket) liveSocket.close();
    };
  } catch (err) {
    console.error("Failed to connect WebSocket:", err);
  }
}

function handleWSMessage(msg) {
  if (msg.type === "INIT_STATE") {
    if (msg.db) updateDBUI(msg.db);
  } else if (msg.type === "DB_HEALTH") {
    updateDBMetrics(msg);
  } else if (msg.type === "DB_MUTATION") {
    fetchDBStatus();
    if (msg.key === "system:accounts") fetchStatus();
  } else if (msg.type === "LOG_ENTRY") {
    appendLog(msg.logger, msg.message, msg.level, msg.is_corrupt_alert);
    if (msg.is_corrupt_alert) {
      showCorruptionAlert("Corruption Alert in Log Stream", msg.message);
    }
  } else if (msg.type === "DB_CORRUPTED") {
    showCorruptionAlert(msg.reason, `Key: ${msg.key} | ${JSON.stringify(msg.details)}`);
    appendLog("CRITICAL_WATCHDOG", `🚨 [DATABASE_CORRUPT] Key: ${msg.key} - ${msg.reason}`, "CRITICAL", true);
  }
}

function appendLog(logger, message, level = "INFO", isAlert = false) {
  const logArea = document.getElementById("liveLogsArea");
  if (!logArea) return;
  const timeStr = new Date().toLocaleTimeString();
  const alertPrefix = isAlert ? "🚨 " : "";
  const line = `[${timeStr}] [${level}] ${alertPrefix}${logger}: ${message}\n`;
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
  const logArea = document.getElementById("liveLogsArea");
  if (logArea) logArea.innerText = "";
}

function showCorruptionAlert(title, message) {
  const banner = document.getElementById("dbCorruptionAlert");
  const titleEl = document.getElementById("alertTitle");
  const msgEl = document.getElementById("alertMessage");
  const healthBadge = document.getElementById("dbHealthBadge");
  if (!banner) return;

  if (titleEl) titleEl.innerText = `🚨 Critical Database Alert: ${title}`;
  if (msgEl) msgEl.innerText = message;
  if (healthBadge) {
    healthBadge.innerText = "CORRUPTED";
    healthBadge.style.background = "rgba(244, 63, 94, 0.25)";
    healthBadge.style.color = "#fb7185";
    healthBadge.style.borderColor = "rgba(244, 63, 94, 0.5)";
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
    if (res.ok) {
      const data = await res.json();
      updateDBUI(data);
    }
  } catch (err) {
    console.warn("Could not fetch DB status:", err);
  }
}

function updateDBUI(st) {
  const engineEl = document.getElementById("dbEngineText");
  const recordsEl = document.getElementById("dbRecordsText");
  const sizeEl = document.getElementById("dbSizeText");
  const healthBadge = document.getElementById("dbHealthBadge");

  if (engineEl) engineEl.innerText = st.engine || "Compiled C (SQLite WAL)";
  if (recordsEl) recordsEl.innerText = `${st.records_count || 0} Binary Records`;
  if (sizeEl) sizeEl.innerText = `${Math.round((st.size_bytes || 0) / 1024 * 10) / 10} KB`;
  if (healthBadge && healthBadge.innerText !== "CORRUPTED") {
    healthBadge.innerText = "Optimal";
    healthBadge.style.background = "rgba(16, 185, 129, 0.15)";
    healthBadge.style.color = "#10b981";
    healthBadge.style.borderColor = "rgba(16, 185, 129, 0.3)";
  }
}

function updateDBMetrics(metrics) {
  const recordsEl = document.getElementById("dbRecordsText");
  const sizeEl = document.getElementById("dbSizeText");
  const healthBadge = document.getElementById("dbHealthBadge");

  if (recordsEl) recordsEl.innerText = `${metrics.record_count || 0} Binary Records`;
  if (sizeEl) sizeEl.innerText = `${Math.round((metrics.size_bytes || 0) / 1024 * 10) / 10} KB`;
  if (healthBadge) {
    if (metrics.integrity_ok) {
      healthBadge.innerText = "Optimal";
      healthBadge.style.background = "rgba(16, 185, 129, 0.15)";
      healthBadge.style.color = "#10b981";
      healthBadge.style.borderColor = "rgba(16, 185, 129, 0.3)";
    } else {
      healthBadge.innerText = "CORRUPTED";
      healthBadge.style.background = "rgba(244, 63, 94, 0.25)";
      healthBadge.style.color = "#fb7185";
      healthBadge.style.borderColor = "rgba(244, 63, 94, 0.5)";
    }
  }
}

async function auditDatabase() {
  try {
    appendLog("Sentinel", "Running deep SQLite B-Tree and CRC32 checksum audit...", "INFO");
    const res = await fetch("/api/db/check", { method: "POST" });
    const data = await res.json();
    if (data.healthy) {
      alert(`✓ Database Audit Passed!\nScanned: ${data.records_scanned} binary records\nStatus: 100% HEALTHY`);
      appendLog("Sentinel", `Audit passed: ${data.records_scanned} records verified, zero corruptions.`, "INFO");
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
  const confirmTest = confirm("Simulate bit-level binary tampering in the compiled database to test instant WebSocket alert and logging?");
  if (!confirmTest) return;

  try {
    appendLog("Simulator", "Injecting simulated binary corruption into 'system:test_block'...", "WARN");
    const res = await fetch("/api/db/test-corrupt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ key: "system:test_block" })
    });
    const data = await res.json();
    appendLog("Simulator", data.message, "WARN");
  } catch (err) {
    alert("Failed to trigger simulation: " + err.message);
  }
}

// Initial fetch and WebSocket bootstrap
fetchStatus();
fetchDBStatus();
initWebSocket();
setInterval(fetchStatus, 8000);
setInterval(fetchDBStatus, 15000);

