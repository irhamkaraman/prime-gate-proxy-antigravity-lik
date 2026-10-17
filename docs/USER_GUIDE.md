# 📚 Prime Gate Antigravity - Complete User & Integration Guide

Welcome to the definitive user manual and integration guide for **Prime Gate Antigravity** (`prime-gate-proxy-antigravity-lik`).

This guide details how to install, authenticate, run, and connect Prime Gate with standard AI coding assistants and OpenAI-compatible tools.

---

## 📑 Table of Contents
1. [Overview & Architecture](#1-overview--architecture)
2. [Installation & Requirements](#2-installation--requirements)
3. [Running the Services](#3-running-the-services)
4. [Account Authentication & Management](#4-account-authentication--management)
5. [Dynamic Model Resolution & Binary Database](#5-dynamic-model-resolution--binary-database)
6. [AI Client & IDE Integration Guide](#6-ai-client--ide-integration-guide)
   - [Cursor IDE](#cursor-ide)
   - [OpenCode](#opencode)
   - [Continue.dev](#continuedev)
   - [Cline / Roo Code](#cline--roo-code)
   - [Aider](#aider)
   - [Python OpenAI SDK](#python-openai-sdk)
   - [Node.js / TypeScript SDK](#nodejs--typescript-sdk)
   - [cURL / Direct HTTP](#curl--direct-http)
7. [Real-Time Reasoning & Thinking Mode](#7-real-time-reasoning--thinking-mode)
8. [Compiled Binary Database & Sentinel Watchdog](#8-compiled-binary-database--sentinel-watchdog)
9. [Token Telemetry & Metrics](#9-token-telemetry--metrics)
10. [CLI Command Reference](#10-cli-command-reference)
11. [Troubleshooting & FAQs](#11-troubleshooting--faqs)

---

## 1. Overview & Architecture

Prime Gate operates as a local proxy gateway that bridges Google's internal Cloud AI Companion / Antigravity service to the standard OpenAI REST and Server-Sent Events (SSE) API specification:

```
[ AI Client / IDE ]
  (Cursor, OpenCode, Continue, Aider)
       │
       ▼ (OpenAI REST / SSE Protocol)
┌────────────────────────────────────────┐
│ Prime Gate Core Gateway (Port 52111)   │
│ - OAuth 2.0 PKCE Token Refresher       │
│ - Dynamic Quota & Tier Resolver        │
│ - Recursive Schema Sanitizer (No 400s) │
│ - Token Telemetry Collector            │
└───────┬────────────────────────┬───────┘
        │                        │
        ▼ (Binary Masked BLOBs)  ▼ (Internal SSE Stream)
┌──────────────────────┐ ┌──────────────────────────────────────┐
│ Compiled Binary DB   │ │ Google Antigravity Cloud             │
│ (data/prime_gate.pgdb│ │ (Claude Sonnet 4.6, Opus 4.6,        │
│  CRC32 Sealed Records│ │  Gemini 3.8 Flash, GPT-OSS 120B)     │
└──────────────────────┘ └──────────────────────────────────────┘
        │ (WebSocket Event Bus)
        ▼
┌────────────────────────────────────────┐
│ Prime Gate Web UI (Port 52110)         │
│ - Stacked Token Bar Chart (Chart.js)   │
│ - Multi-Account Quota Radar            │
│ - Prompt Sandbox with [THINKING] tags  │
│ - Database Sentinel Watchdog Terminal  │
└────────────────────────────────────────┘
```

---

## 2. Installation & Requirements

### System Requirements:
- **Operating System:** Windows 10/11, macOS, or Linux.
- **Python:** 3.10, 3.11, or 3.12.
- **Node.js:** 18.x or 20.x+ (for Web UI dashboard).

### Step-by-Step Installation:
```bash
# 1. Clone repository
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik

# 2. Install Python dependencies
pip install -r requirements.txt
```
*(Windows users can simply double-click `scripts\install.bat`)*

---

## 3. Running the Services

Prime Gate consists of two core components:
1. **Core API Gateway:** `http://127.0.0.1:52111`
2. **Web UI Dashboard:** `http://127.0.0.1:52110`

### Mode A: One-Click Windows Launcher (Recommended)
Double-click `scripts\start-all.bat` or run:
```cmd
scripts\start-all.bat
```
This boots both the API proxy and the Web UI in the background and opens the dashboard in your browser.

### Mode B: CLI Background Daemon
```bash
# Start background daemon
python -m prime_gate.cli daemon start

# Check status (PID, memory, port)
python -m prime_gate.cli daemon status

# Stop background daemon
python -m prime_gate.cli daemon stop
```

### Mode C: Foreground Terminal Mode
Run in two separate terminals:
```bash
# Terminal 1: Core Proxy
python -m prime_gate.cli start --port 52111

# Terminal 2: Web UI
python -m prime_gate.cli ui --port 52110
```

---

## 4. Account Authentication & Management

### Web UI Setup Onboarding:
1. Navigate to **`http://127.0.0.1:52110`**.
2. If no account is connected, the setup overlay appears automatically.
3. Choose either:
   - **"Sign in with Google"**: Authorizes via Google OAuth 2.0 PKCE in your default browser.
   - **"⚡ Quick Import from OpenCode Config"**: Reads credentials from `~/.config/opencode/antigravity-accounts.json`.

### Terminal CLI Commands & Flags:
```bash
# Authenticate via browser
python -m prime_gate.cli auth login

# Import existing OpenCode accounts
python -m prime_gate.cli auth import

# List connected accounts and detected tiers
python -m prime_gate.cli auth list

# Delete a specific account via positional email or interactive menu
python -m prime_gate.cli auth remove user@gmail.com

# Delete a specific account via flag with forced confirmation bypass
python -m prime_gate.cli auth remove --email user@gmail.com --force
# (Short form: python -m prime_gate.cli delete-account -e user@gmail.com -f)

# Delete ALL accounts via flag without interactive prompt
python -m prime_gate.cli auth remove --all --force
# (Alternative: python -m prime_gate.cli auth clear -y)
```

### Web UI Account Management & Deletion:
1. Open the **Account Manager** tab in the sidebar.
2. In the **Active Identity** card:
   - Click the red **"Delete Account"** button to permanently remove the currently active account.
3. In the **Configured Accounts** deck:
   - Every connected account has an individual red **"Delete"** button with a trash icon to delete that specific account.
4. To wipe all connected accounts at once, click the red **"Clear All"** button in the top action bar. If all accounts are deleted, the Web UI automatically returns to the initial setup onboarding overlay.

---

## 5. Dynamic Model Resolution & Binary Database

Prime Gate automatically queries Google Antigravity servers upon:
1. **First Login / Import:** Pulls all valid models and live quotas.
2. **Daemon Startup:** Loads models instantly from `data/prime_gate.pgdb` with zero latency, while a background task refreshes the catalog from Google.
3. **Manual Refresh:** Triggered via the **`↻ Refresh Quota & Models`** button in the Web UI or `prime-gate check-models` in the CLI.

The static definitions in `prime_gate/config.py` serve strictly as a **bootstrap offline fallback** if the system has no network connectivity.

---

## 6. AI Client & IDE Integration Guide

All OpenAI-compatible clients use:
- **Base URL:** `http://127.0.0.1:52111/v1`
- **API Key:** `prime-gate-proxy` (any non-empty string)

### Cursor IDE
1. Open Cursor Settings (**Ctrl+,** / **Cmd+,**).
2. Go to **Features** &gt; **Models**.
3. Under **OpenAI API Key**, enter `prime-gate-proxy`.
4. Enable **Override OpenAI Base URL** and enter:
   ```text
   http://127.0.0.1:52111/v1
   ```
5. Add models:
   - `claude-sonnet-4-6`
   - `gemini-3.8-flash`
   - `claude-opus-4-6-thinking`

### OpenCode
Edit `~/.config/opencode/opencode.json`:
```json
{
  "providers": {
    "antigravity": {
      "baseUrl": "http://127.0.0.1:52111/v1",
      "apiKey": "prime-gate-proxy",
      "models": [
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gemini-3.8-flash",
        "gemini-3.8-flash-high",
        "gemini-3.1-flash-lite",
        "gpt-oss-120b-medium"
      ]
    }
  }
}
```

### Continue.dev
Edit `~/.continue/config.json`:
```json
{
  "models": [
    {
      "title": "Claude Sonnet 4.6 (Prime Gate)",
      "provider": "openai",
      "model": "claude-sonnet-4-6",
      "apiBase": "http://127.0.0.1:52111/v1",
      "apiKey": "prime-gate-proxy"
    },
    {
      "title": "Gemini 3.8 Flash (Prime Gate)",
      "provider": "openai",
      "model": "gemini-3.8-flash",
      "apiBase": "http://127.0.0.1:52111/v1",
      "apiKey": "prime-gate-proxy"
    }
  ]
}
```

### Cline / Roo Code
1. Open Cline Settings.
2. Select API Provider: **OpenAI Compatible**.
3. Base URL: `http://127.0.0.1:52111/v1`.
4. API Key: `prime-gate-proxy`.
5. Model ID: `claude-sonnet-4-6` or `gemini-3.8-flash`.

### Aider
```bash
aider --openai-api-base http://127.0.0.1:52111/v1 \
      --openai-api-key prime-gate-proxy \
      --model openai/claude-sonnet-4-6
```

### Python OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:52111/v1",
    api_key="prime-gate-proxy"
)

response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[{"role": "user", "content": "Write a thread-safe singleton in Python."}],
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(f"[THINKING] {delta.reasoning_content}", end="", flush=True)
    if delta.content:
        print(delta.content, end="", flush=True)
```

### Node.js / TypeScript SDK
```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:52111/v1",
  apiKey: "prime-gate-proxy",
});

async function run() {
  const stream = await client.chat.completions.create({
    model: "gemini-3.8-flash",
    messages: [{ role: "user", content: "Explain CRDTs briefly." }],
    stream: true,
  });

  for await (const chunk of stream) {
    process.stdout.write(chunk.choices[0]?.delta?.content || "");
  }
}

run();
```

### cURL / Direct HTTP
```bash
curl -X POST http://127.0.0.1:52111/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer prime-gate-proxy" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Hello!"}],
    "stream": false
  }'
```

---

## 7. Real-Time Reasoning & Thinking Mode

Prime Gate extracts Google Antigravity's internal reasoning thoughts and forwards them via OpenAI-standard SSE delta payloads:
```json
{
  "choices": [
    {
      "index": 0,
      "delta": {
        "reasoning_content": "Evaluating edge cases for concurrency locks..."
      }
    }
  ]
}
```

In the Web UI Prompt Sandbox, reasoning tokens are visualised within `[THINKING] ... [/THINKING]` badges before the main completion text appears.

---

## 8. Compiled Binary Database & Sentinel Watchdog

Prime Gate does **NOT** store plaintext JSON files:
- **Database Location:** `data/prime_gate.pgdb` (SQLite WAL format).
- **Binary Obfuscation:** Credentials, OAuth tokens, and quotas are packed into binary records (`REC_ACCOUNT`, `REC_MODEL`, `REC_QUOTA`).
- **Cryptographic CRC32 Integrity:** Every record is verified with a 32-bit CRC32 checksum before being decoded.
- **Autonomous Sentinel Watchdog:** Audits the binary file every 5 seconds. If bytes are altered or corrupted, an alert is broadcast over WebSocket (`/ws/live`) to the Web UI console.

---

## 9. Token Telemetry & Metrics

The dashboard features real-time token tracking rendered via local Chart.js:
- **1s Resolution:** Token velocity over the last 60 seconds.
- **1m Resolution:** Token usage over the last 30 minutes.
- **1h Resolution:** Hourly token breakdown over the last 24 hours.
- **1d Resolution:** Daily consumption across the past 14 days.

Metrics distinguish between:
1. **Prompt Tokens**
2. **Completion Tokens**
3. **Reasoning Tokens** (Deep thinking chain-of-thought tokens)

---

## 10. CLI Command Reference

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `prime-gate --version` | None | Displays version, codename, and system runtime. |
| `prime-gate quota` | `--refresh` | Prints quota percentage bar and active model table. |
| `prime-gate check-models` | `--refresh` | Queries live models from Google Antigravity servers. |
| `prime-gate auth login` | `--port` | Launches browser for Google OAuth 2.0 PKCE. |
| `prime-gate auth import` | None | Imports accounts from OpenCode configuration. |
| `prime-gate auth list` | None | Lists connected accounts and detected tiers. |
| `prime-gate auth remove [EMAIL]` | `[EMAIL]`, `-e/--email`, `-a/--all`, `-f/--force` | Removes account(s) via positional arg, flags, or interactive prompt. |
| `prime-gate delete-account` | `[EMAIL]`, `-e/--email`, `-a/--all`, `-f/--force` | Direct shortcut to delete account(s) via flag or interactive menu. |
| `prime-gate auth clear` | `-y/--yes`, `-f/--force` | Wipes all accounts and resets database state. |
| `prime-gate daemon start` | None | Launches background proxy & web UI on Windows. |
| `prime-gate daemon status` | None | Checks background PID, memory, and port health. |
| `prime-gate daemon stop` | None | Terminates active background proxy processes. |
| `prime-gate db status` | None | Shows binary DB file size and record counts. |
| `prime-gate db check` | None | Performs full CRC32 cryptographic audit. |
| `prime-gate start` | `--port`, `--host` | Runs FastAPI server in foreground terminal. |
| `prime-gate ui` | `--port`, `--api-port` | Starts Node.js Web UI server in foreground. |

---

## 11. Troubleshooting & FAQs

### Q: Why did I receive "503 Service Unavailable: MODEL_CAPACITY_EXHAUSTED"?
**A:** Legacy models like `gemini-2.5-pro` and `gemini-2.5-flash` have severe upstream server constraints. Prime Gate has removed them from the default catalog. Please switch to **`gemini-3.8-flash`** or **`claude-sonnet-4-6`**, which have ample capacity.

### Q: How do I resolve "Address already in use (Errno 10048)"?
**A:** A previous instance of Prime Gate is running. Stop it with:
```bash
python -m prime_gate.cli daemon stop
```
Or start Prime Gate on a different port:
```bash
python -m prime_gate.cli start --port 52120
python -m prime_gate.cli ui --port 52121 --api-port 52120
```

### Q: Can my OAuth credentials or tokens leak to GitHub?
**A:** No. All sensitive data is stored inside `data/prime_gate.pgdb`, which is ignored by `.gitignore`. No plaintext tokens or secrets exist in the repository.
