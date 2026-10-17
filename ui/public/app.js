/**
 * Prime Gate Antigravity - System Dashboard Logic (Anthropic Theme)
 */

async function fetchStatus() {
  const indicator = document.getElementById("statusIndicator");
  const statusText = document.getElementById("statusText");

  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("API unreachable");
    const data = await res.json();

    indicator.className = "status-pill online";
    statusText.innerText = "Connected & Active";

    document.getElementById("accountTier").innerText = data.tier || "Active Plan";
    document.getElementById("accountEmail").innerText = data.active_account || "No Account Configured";
    document.getElementById("accountCount").innerText = `${data.total_accounts} Configured`;

    const uptimeMins = Math.floor(data.uptime / 60);
    const uptimeSecs = data.uptime % 60;
    document.getElementById("serverUptime").innerText = `${uptimeMins}m ${uptimeSecs}s`;

    renderQuota(data.quota || []);
    fetchModels();
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
    const json = await res.json();
    const models = json.data || [];

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
          const parsed = json.parse(jsonStr);
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
        } catch (e) {}
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

// Initial fetch and auto-refresh every 8 seconds
fetchStatus();
setInterval(fetchStatus, 8000);
