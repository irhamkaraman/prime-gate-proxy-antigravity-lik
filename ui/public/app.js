async function fetchStatus() {
  const indicator = document.getElementById("statusIndicator");
  const statusText = document.getElementById("statusText");

  try {
    const res = await fetch("/api/status");
    if (!res.ok) throw new Error("API Offline");
    const data = await res.json();

    indicator.className = "status-indicator online";
    statusText.innerText = "Online & Connected";

    document.getElementById("accountTier").innerText = data.tier || "Unknown";
    document.getElementById("accountEmail").innerText = data.active_account || "Belum Login";
    document.getElementById("accountCount").innerText = `${data.total_accounts} Akun Terdaftar`;

    const uptimeMins = Math.floor(data.uptime / 60);
    const uptimeSecs = data.uptime % 60;
    document.getElementById("serverUptime").innerText = `${uptimeMins}m ${uptimeSecs}s`;

    renderQuota(data.quota || []);
    fetchModels();
  } catch (err) {
    indicator.className = "status-indicator offline";
    statusText.innerText = "Python API Offline";
    document.getElementById("quotaContainer").innerHTML = `
      <div style="color: #ef4444; font-size: 13px; padding: 10px;">
        ⚠️ Python Core API tidak terdeteksi. Jalankan <code>prime-gate start</code> atau <code>prime-gate daemon start</code> di terminal.
      </div>
    `;
  }
}

function renderQuota(quotaList) {
  const container = document.getElementById("quotaContainer");
  if (!quotaList || quotaList.length === 0) {
    container.innerHTML = '<div style="color: #94a3b8; font-size: 13px;">Tidak ada data kuota aktif.</div>';
    return;
  }

  container.innerHTML = quotaList.map(item => {
    const pct = item.percentage;
    let color = "#34d399"; // green
    if (pct < 20) color = "#ef4444"; // red
    else if (pct < 50) color = "#f59e0b"; // yellow

    return `
      <div class="quota-item">
        <div class="quota-info">
          <span class="quota-title">${item.label}</span>
          <span class="quota-pct" style="color: ${color}">${pct}%</span>
        </div>
        <div class="quota-bar-bg">
          <div class="quota-bar-fill" style="width: ${pct}%; background: ${color};"></div>
        </div>
        <div class="quota-reset">Reset: ${item.reset_time}</div>
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

    document.getElementById("modelCountBadge").innerText = `${models.length} Model`;

    const grid = document.getElementById("modelsGrid");
    grid.innerHTML = models.map(m => `
      <div class="model-item">
        <div class="model-name">${m.id}</div>
        <div class="model-id">Provider: ${m.owned_by}</div>
      </div>
    `).join("");

    // Populate sandbox select
    const select = document.getElementById("modelSelect");
    select.innerHTML = models.map(m => `
      <option value="${m.id}">${m.id}</option>
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
    alert("Ketik instruksi/prompt terlebih dahulu!");
    return;
  }

  const model = modelSelect.value;
  outputArea.innerText = "Menghubungkan ke Google Antigravity...";
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
      outputArea.innerText = `Error (${response.status}):\n${errText}`;
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
        } catch (e) {}
      }
    }
  } catch (err) {
    outputArea.innerText = `Koneksi gagal: ${err.message}`;
  } finally {
    sendBtn.disabled = false;
  }
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text);
  alert("Endpoint URL disalin ke clipboard: " + text);
}

// Initial fetch & auto poll every 10 seconds
fetchStatus();
setInterval(fetchStatus, 10000);
