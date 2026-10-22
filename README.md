<div align="center">

<img src="docs/images/prime_gate_dual_protocol.svg" alt="Prime Gate Dual Protocol - OpenAI & Anthropic Compatible Gateway for Google Antigravity" width="100%" />

<br/><br/>

# ⚡ Prime Gate Antigravity Proxy
### `prime-gate-proxy-antigravity-lik`

**A Production-Grade, Self-Hosted OpenAI & Anthropic Compatible Proxy Gateway for Google Antigravity.**

[![Version](https://img.shields.io/badge/version-1.2.4-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![CI](https://img.shields.io/badge/CI-Passing-brightgreen.svg?style=for-the-badge&logo=githubactions&logoColor=white)](.github/workflows/ci.yml)
[![Security](https://img.shields.io/badge/Security-Client%20Alignment-blue.svg?style=for-the-badge&logo=shield)](#-request-safety--client-alignment)
[![Semantic Cache](https://img.shields.io/badge/Cache-Semantic%20Vector%20FastEmbed-a78bfa.svg?style=for-the-badge)](README.md#-next-gen-smart--semantic-vector-caching-hybrid-engine)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-blueviolet.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)

---

### 🌐 Select Language & Documentation

[🇺🇸 English](README.md) • [🇮🇩 Bahasa Indonesia](locales/id/README.md) • [🇨🇳 简体中文](locales/zh/README.md) • [🇷🇺 Русский](locales/ru/README.md) • [🇯🇵 日本語](locales/ja/README.md) • [🇩🇪 Deutsch](locales/de/README.md) • [🇫🇷 Français](locales/fr/README.md)

📚 **Guides:** [User Guide](docs/USER_GUIDE.md) • [Testing & Conformance](docs/testing.md) • [Observability & Metrics](docs/observability.md) • [Benchmark Methodology](benchmarks/METHODOLOGY.md)

---

</div>

## ⚠️ Disclaimer & Risks

> [!WARNING]
> **Unofficial Project & Use at Your Own Risk:**
> - **Prime Gate Antigravity Proxy** is an independent open-source project and is **NOT affiliated with, endorsed, or approved** by Google LLC or Anthropic PBC.
> - Using this proxy to access Google Cloud AI Companion / Antigravity internal services outside the official VS Code extension **may potentially violate Google Cloud Terms of Service**.
> - All usage risks lie entirely with the user. The developers and maintainers assume no responsibility for any consequences, including quota restrictions, account suspension, or termination of the Google account used.
> - **ACCOUNT SECURITY NOTICE:** **NEVER** use your primary Google account, important personal email, or corporate/organization accounts. It is strongly recommended to use only a secondary or dedicated experimental Google account.

---

## 📖 Overview

**Prime Gate** is an enterprise-ready, dual-protocol API bridge that wraps Google's internal Cloud AI Companion / Antigravity service into both **100% OpenAI-compliant** (`/v1/chat/completions`) and **native Anthropic Messages API compliant** (`/v1/messages`) REST & SSE endpoints.

It allows you to use your Google Antigravity quotas—including **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)**, and **Gemini 3.8 Flash**—directly inside any standard AI coding tool, such as **Claude Code CLI**, **Cline**, **Roo Code**, **OpenCode**, **Cursor**, **Continue.dev**, **Aider**, and **SillyTavern**.

---

## 🔍 Known Limitations

1. **Upstream Quota Dependency:** Inference quotas, model availability, and request rate limits are entirely determined by Google Cloud server policies.
2. **Internal API Schema Drift:** Because it operates against internal Google Antigravity APIs, sudden upstream schema changes may affect translation functionality until an adaptive update is released.
3. **Public Web Search:** MCP Web Search (`scripts/mcp_search.py`) relies on public DoH resolvers (Cloudflare 1.1.1.1) and DuckDuckGo HTML parsers that may experience format changes at any time.
4. **Not a Commercial API Replacement:** This project is designed for personal developer workflows and local experimentation, not large-scale commercial production workloads.

---

## 🛡️ Threat Model

To maintain technical transparency, the following matrix outlines what is protected (in-scope) and what lies outside system control (out-of-scope):

| Area / Component | In-Scope Protection | Out-of-Scope (Not Protected) |
| :--- | :--- | :--- |
| **Local Credentials & Tokens** | AES-256-GCM authenticated encryption with a unique 12-byte random nonce per record and AAD binding. Master key isolated in OS Keyring (Windows DPAPI, macOS Keychain, Linux SecretService) with Scrypt KDF fallback. Tokens automatically excluded from Git tracking. | Protection against active malware or processes running with root/administrator privileges on your local operating system. |
| **Database Integrity** | 32-bit CRC32 checksum detects physical bit-rot / disk corruption, while AES-256-GCM authentication tags detect deliberate data tampering. Automatic pre-migration snapshots stored in `data/backups/`. | Irrecoverable hardware failure. Use `prime-gate db rollback` to recover from existing local backups. |
| **Authentication & Access Boundaries** | All proxy endpoints (`/v1/*`) mandate API Key authentication (`Authorization: Bearer` or `x-api-key`). Keys are stored strictly as salted SHA-256 hashes. Non-loopback host bindings are prevented from unauthenticated exposure. | Accidental sharing or leakage of raw API keys by the user to third parties. |
| **Dashboard & Localhost Security** | DNS Rebinding mitigation (`Host` header validation), `Origin` validation, double-submit CSRF tokens, `HttpOnly` `SameSite=Strict` sessions, and modern security headers (CSP, nosniff, DENY, Referrer-Policy). WebSocket `/sentinel` handshake validates session and origin. | Third-party browser extensions with elevated permissions to inspect cookies or manipulate the local DOM. |
| **Client Traffic Patterns** | HTTP/gRPC header normalization mimicking official IDE extensions, humanized pacing, and Sentinel Loop Guard (breaking $\ge 3$ repetitive identical tool calls). | Server-side Google network analysis (IP inspection, behavioral audits). **Zero guarantees against upstream server-side detection or bans.** |
| **Quota Consumption** | Local semantic vector cache (~12ms) reduces duplicate queries to upstream. | Adjustments to quota limits, daily reset thresholds, or subscription policies by Google. |

---

## 🌟 Key Architecture & Highlights

```mermaid
graph LR
    Client["AI Client (Cursor / Cline / OpenCode / Claude Code)"] 
    -->|"OpenAI (/v1) & Anthropic (/v1/messages)"| PyCore["Python Core Gateway (FastAPI :52111)"]
    
    subgraph "Prime Gate System"
        PyCore -->|"Token Refresh / PKCE"| Auth["Auth & Accounts Manager"]
        PyCore -->|"Quota & Tier Resolver"| Quota["Quota Monitor"]
        PyCore -->|"Bidirectional Protocols"| Translator["Anthropic & OpenAI Translators"]
        PyCore -->|"Compactor & Loop Guard"| Enterprise["Enterprise Engine"]
        PyCore -->|"Hybrid Vector Engine"| Cache["FastEmbed Semantic Cache"]
        UI["Node.js Web UI (:52110)"] <-->|"Status & Proxy"| PyCore
    end

    PyCore -->|"Daily CloudCode Internal API"| Google["Google Antigravity Cloud"]
```

### 🎯 Core Capabilities:
1. **Dual-Protocol Compliant (OpenAI & Anthropic Native):**
   Full drop-in support for both OpenAI (`/v1/chat/completions`) and Anthropic Messages API (`/v1/messages`, `/v1/messages/count_tokens`).
2. **Native Anthropic Protocol Translation:**
   Seamlessly connects **Claude Code CLI, Cline, Roo Code, Cursor (Claude mode), Continue.dev, and LibreChat** directly to Prime Gate without any third-party proxy adapters.
3. **Strict 7-Event Anthropic Streaming State Machine:**
   Implements full Anthropic SSE streaming: `message_start`, `content_block_start`, `content_block_delta` (`text_delta` & `input_json_delta`), `content_block_stop`, `message_delta`, and `message_stop`.
4. **Pre-flight Token Counting Endpoint (`POST /v1/messages/count_tokens`):**
   Enables autonomous coding agents (Cline, Roo Code, Claude Code) to accurately budget context windows before sending inferences.
5. **Real-time Reasoning / Thinking Stream:**
   Natively streams deep thinking blocks via `choices[0].delta.reasoning_content` for Claude 4.6 Thinking and Gemini 3.8.
6. **Zero 400 Bad Request (Recursive Schema Sanitizer):**
   Eliminates Google Antigravity's strict schema errors (`exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`) for 100% stable Tool Calling & Function Execution.
7. **Intelligent Quota & Tier Detection:**
   Distinguishes between **`Google AI Pro (Trial Tier)`** and **`Google AI Pro (Paid Tier)`**, automatically presenting only valid model catalogs.
8. **Modern React & TypeScript SPA Dashboard with Dedicated Page Routes:**
   Built with Vite and strict TypeScript, featuring dedicated page routes (`/dashboard`, `/accounts`, `/sandbox`, `/caching`, `/sentinel`, `/docs`), instant HMR, sourcemap debugging, real-time token telemetry, interactive Prompt Sandbox with OpenAI/Anthropic protocol toggle, and Database Sentinel diagnostics.
9. **Rich Terminal CLI Suite:**
   Modern terminal interface featuring `--version`, `quota`, `auth list|import|login|remove|clear`, `db status|check|test-corrupt`, and headless Windows background `daemon` management.
10. **SQLite WAL Database with AES-256-GCM Encryption & CRC32 Integrity Checking:**
    Stores configuration and session records in an SQLite database with Write-Ahead-Logging (WAL) mode. Sensitive OAuth tokens and credentials are encrypted at-rest using AES-256-GCM with hardware-backed OS Keyring key management (DPAPI/Keychain/SecretService) and 32-bit CRC32 checksums for disk integrity verification.
11. **Smart Agent Context Compactor:**
    Automatically prunes verbose tool output history older than 3 active turns while preserving system instructions and recent context, reducing 30k–100k agent prompts by 50% to 70%.
12. **Mid-Flight Transparent Account Failover:**
    Catches upstream Google Antigravity HTTP 429 (`RESOURCE_EXHAUSTED`) / 503 errors and rotates to the next healthiest account before emitting the first stream token—zero client drops.
13. **AI Agent Runaway Loop Killer & Sentinel Guard:**
    Detects infinite repetitive tool calls ($\ge 3$ consecutive identical calls) and injects corrective system instructions to stop execution loops and halt quota drain.
14. **Commercial API Tariff Equivalent Estimator:**
    Calculates estimated comparative value against official OpenAI/Anthropic commercial rates (GPT-4o / Claude 3.5 Sonnet benchmarks) in USD and IDR. Note: Users utilize their own active Google subscription quotas.
15. **Request Normalization & Companion Client Alignment:**
    Aligns request structure and headers with official Google Cloud Code client patterns, uses standard OAuth 2.0 PKCE token refresh, normalizes payloads, and implements request pacing to avoid burst flags.
16. **Next-Gen Smart & Semantic Vector Caching (Hybrid Engine):**
    Eliminates the 100% cache miss on AI coding agents by separating tool declarations from tool executions. Features local FastEmbed ONNX vector embeddings (`BAAI/bge-small-en-v1.5`), high-speed cosine similarity scanning in SQLite WAL, turn-based key extraction, smooth token-chunked SSE replay, and upstream prefix caching optimization.

---

## 🛡️ Request Safety & Client Alignment

Prime Gate implements structured request handling to maintain protocol alignment with Google Cloud upstream services:

| Technical Layer | Implementation Mechanism | Purpose & Behavior |
| :--- | :--- | :--- |
| **1. Client Header Alignment** | Normalizes HTTP/gRPC headers to resemble official Cloud Code IDE extensions. | Ensures metadata structures are accepted and parsed smoothly by upstream APIs. |
| **2. Native OAuth 2.0 PKCE** | Standard cryptographic token exchange with automatic periodic token refresh. | Prevents session hijacking and eliminates reliance on unofficial browser cookies. |
| **3. Request Pacing & Jitter Smoothing** | Natural interval distribution, exponential backoff, and traffic smoothing. | Mitigates burst traffic spikes that trigger upstream rate limiting. |
| **4. Mid-Flight Account Failover** | Automatic rotation to the next healthy account upon encountering 429/503 limits. | Preserves user inference continuity before the first stream token is emitted. |
| **5. Sentinel Runaway Loop Killer** | Detects and interrupts repetitive identical tool call loops ($\ge 3$ cycles). | Halts recursive agent execution loops to prevent quota drainage. |
| **6. Clean Schema Sanitization** | Strips unsupported OpenAPI attributes before transmitting payloads upstream. | Eliminates upstream schema validation failures (`400 Bad Request`). |

---

## 📸 User Interface & Demonstration

Explore Prime Gate's Anthropic-inspired dark glassmorphism interface, built with React 18, TypeScript, and high-performance WebSockets:

### 1. Dashboard & Real-Time Telemetry (`/dashboard`)
Visualizes live token consumption, active throughput speed, rolling 24-hour token totals, average time-to-first-token (TTFT) latency, segmented token volume breakdowns (`1m`, `1h`, `1d`, `1month`), and a leaderboard preview of top token spenders and quota drainers.
![Dashboard & Telemetry](docs/images/dashboard-telemetry.png)

### 2. Usage & Model Benchmarks (`/benchmarks`)
Persistent SQLite WAL-backed ledger recording every inbound API request hit in real time. Surfaces model analytics, latency benchmarks, token volume shares, and weighted Quota Impact scoring (Claude 3x, GPT 2x, Gemini 1x) with instant search, filtering, and copyable request IDs.
![Usage & Benchmarks](docs/images/usage-benchmarks.png)

### 3. Account Manager & Dynamic Model Catalog (`/accounts`)
Multi-account OAuth management with active account rotation, quota depletion status, and automatic model catalog discovery with capability badges (Thinking Supported, Vision/Multimodal, Context Window, Streaming).
![Account Manager & Models](docs/images/accounts-models.png)

### 4. Prompt Sandbox & Playground (`/sandbox`)
Interactive test bench for streaming model completions. Configure system prompts, user messages, temperature, and token budgets with real-time inference telemetry (TTFT, total generation time, tokens per second).
![Prompt Sandbox](docs/images/prompt-sandbox.png)

### 5. System & Database Sentinel (`/sentinel`)
Auditing console for high-speed binary SQLite storage in WAL mode. Inspects header CRC32 integrity, page cache allocation, database vacuuming, and live daemon background audit logs over bidirectional WebSockets.
![System Sentinel](docs/images/system-sentinel.png)

---

## ⚡ Quick Start

### 1. Clone & Install
```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt
```
*(Windows users can simply double-click `scripts\install.bat`)*

### 2. Launch Background Daemon & Web UI
Start both the Python Core API and Node.js Web UI with a single command:
- **Windows (One-Click Background Launcher):**
  ```bash
  scripts\start-all.bat
  ```
- **Or via CLI Daemon:**
  ```bash
  python -m prime_gate.cli daemon start
  ```
- **Or Foreground Terminal Mode:**
  ```bash
  # Terminal 1: Core API
  python -m prime_gate.cli start --port 52111

  # Terminal 2: Web UI
  python -m prime_gate.cli ui --port 52110
  ```

### 3. Open Web UI Onboarding & Connect Account
1. Open your browser and navigate to **`http://127.0.0.1:52110`**.
2. If you haven't logged in yet, the **Anthropic-styled Setup Onboarding** overlay will appear automatically:
   - Click **"Sign in with Google"** to authenticate via Google OAuth 2.0 PKCE.
   - Or click **"⚡ Quick Import from OpenCode Config"** if you already have accounts saved in OpenCode.
3. Once authenticated, Prime Gate automatically transitions into the main **System Dashboard**, activating your live Quota Radar, active model catalog, and OpenAI endpoint (`http://127.0.0.1:52111/v1`).

> 💡 **CLI Alternative:** Prefer CLI setup? You can also authenticate directly in terminal:
> ```bash
> python -m prime_gate.cli auth login   # Sign in via browser OAuth
> python -m prime_gate.cli auth import  # Import OpenCode config
> python -m prime_gate.cli quota        # View live quota table
> ```

---

## 💻 CLI Command Reference

Execute commands using `python -m prime_gate.cli` or `bin\prime-gate.cmd`:

| Command | Description |
| :--- | :--- |
| `prime-gate --version` | Display version, runtime info, and codename. |
| `prime-gate --help` | Show complete interactive command list. |
| `prime-gate quota` | Display real-time quota status table & active model catalog. |
| `prime-gate check-models` | Auto-load live supported models directly from Google Antigravity servers. |
| `prime-gate auth list` | Show all stored Google Antigravity accounts. |
| `prime-gate auth import` | Import accounts from `~/.config/opencode/antigravity-accounts.json`. |
| `prime-gate auth switch [EMAIL]` | Switch the active Antigravity account (positional, flag `-e`, or interactive). |
| `prime-gate auth login` | Open browser for Google OAuth 2.0 PKCE authentication. |
| `prime-gate auth remove [EMAIL]` | Remove account (or pick interactively from a numbered menu). |
| `prime-gate auth remove -e <email> -f` | Delete account via flag with forced confirmation bypass (`--email`, `--force`). |
| `prime-gate auth remove -a -f` | Delete ALL accounts via flags without prompt (`--all`, `--force`). |
| `prime-gate delete-account [email]` | Direct top-level shortcut to delete account or all accounts. |
| `prime-gate auth clear -y` | Remove all stored accounts and reset to initial onboarding state. |
| `prime-gate daemon start` | Launch proxy & web UI in the background (headless). |
| `prime-gate daemon status` | Check background process PID, memory, and ports. |
| `prime-gate daemon stop` | Terminate all active background proxy services. |
| `prime-gate auth create-key [--name NAME]` | Generate a new random API key (displayed once, saved as salted SHA-256). |
| `prime-gate auth list-keys` | Display registered API key IDs, names, policies (RPM/TPD), allowed models, and scopes. |
| `prime-gate auth revoke-key <ID|NAME>` | Immediately revoke an API key by ID or name. |
| `prime-gate db check` | Run 32-bit CRC32 cryptographic audit on binary database. |
| `prime-gate db rotate-key` | Rotate AES-256-GCM master database key and re-encrypt all records. |
| `prime-gate db rollback` | Roll back SQLite database to the most recent pre-migration or manual backup. |
| `prime-gate start` | Run API server in foreground with live request logs. |
| `prime-gate ui` | Start and open the Node.js Web UI Dashboard. |

### 🔄 Account Switching (Web UI & CLI):
Prime Gate allows seamless switching between multiple Google Antigravity accounts with immediate model and quota synchronization:
- **In Web UI Sidebar:** Use the **Active Account** dropdown selector at the bottom of the sidebar to switch active credentials on the fly from any view.
- **In Web UI Accounts Tab:** Click the amber **"Set Active"** button on any registered account card.
- **Via CLI:**
  ```bash
  python -m prime_gate.cli auth switch user@gmail.com
  # Or with flag:
  python -m prime_gate.cli auth switch -e user@gmail.com
  # Or select interactively from a numbered menu:
  python -m prime_gate.cli auth switch
  ```

### 🗑️ Account Deletion & Management Flags:
Prime Gate provides flexible flags to remove individual or all accounts from both terminal and Web UI:
- **Delete specific account via flag:**
  ```bash
  python -m prime_gate.cli auth remove --email user@gmail.com --force
  # Or via shortcut:
  python -m prime_gate.cli delete-account -e user@gmail.com -f
  ```
- **Delete ALL accounts without prompt:**
  ```bash
  python -m prime_gate.cli auth remove --all --force
  ```
- **Interactive selection:**
  Run `python -m prime_gate.cli auth remove` without arguments to select from a numbered list of registered accounts.
- **In Web UI:**
  Navigate to the **Account Manager** tab, click the red **"Delete"** button on any account card or **"Delete Account"** on the Active Identity card. Click **"Clear All"** to wipe all accounts.

---

## 🔌 AI Client Integration & Setup Guide

Prime Gate provides a dual-protocol high-performance gateway:
- **Anthropic Messages Protocol:** `http://127.0.0.1:52111/v1/messages` (Native SSE streaming, tool-calling, extended thinking)
- **OpenAI Compatible Protocol:** `http://127.0.0.1:52111/v1` (Chat completions, model listing, health telemetry)

Use an authorized API key generated via `prime-gate auth create-key` (e.g. `pg-live-...`) or the default key generated on initial startup.

---

### 1. Claude Code CLI (Anthropic Native)

Prime Gate includes native Anthropic Messages API support engineered specifically for [Claude Code CLI](https://docs.anthropic.com/en/docs/agents-and-tools/claude-code/overview), supporting full bidirectional tool calling, massive harness system prompts (>4k chars), and deep agentic coding loops.

#### Quick Start (Current Terminal Session):
- **Windows PowerShell:**
  ```powershell
  $env:ANTHROPIC_BASE_URL="http://127.0.0.1:52111"
  $env:ANTHROPIC_API_KEY="pg-live-your-key-here"
  $env:ANTHROPIC_MODEL="gemini-3.8-flash"  # or claude-sonnet-4-6
  claude
  ```
- **macOS / Linux (Bash / Zsh):**
  ```bash
  export ANTHROPIC_BASE_URL="http://127.0.0.1:52111"
  export ANTHROPIC_API_KEY="pg-live-your-key-here"
  export ANTHROPIC_MODEL="gemini-3.8-flash"  # or claude-sonnet-4-6
  claude
  ```

#### Persistent Configuration:
- **Windows (Permanent User Environment):**
  ```powershell
  [System.Environment]::SetEnvironmentVariable("ANTHROPIC_BASE_URL", "http://127.0.0.1:52111", "User")
  [System.Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "prime-gate-proxy", "User")
  [System.Environment]::SetEnvironmentVariable("ANTHROPIC_MODEL", "gemini-3.8-flash", "User")
  ```
- **macOS / Linux (Add to `~/.bashrc` or `~/.zshrc`):**
  ```bash
  echo 'export ANTHROPIC_BASE_URL="http://127.0.0.1:52111"' >> ~/.bashrc
  echo 'export ANTHROPIC_API_KEY="pg-live-your-key-here"' >> ~/.bashrc
  echo 'export ANTHROPIC_MODEL="gemini-3.8-flash"' >> ~/.bashrc
  source ~/.bashrc
  ```

#### Common Commands:
```bash
# Start interactive agent session
claude

# Single-prompt execution (scriptable)
claude -p "Explain the architecture of this repository"

# Explicit model selection on startup
claude --model gemini-3.8-flash
claude --model claude-sonnet-4-6
```

> ⚡ **Engine Note:** Claude Code CLI dispatches 28 tool declarations and a ~4,500-character system harness. Prime Gate automatically normalizes and injects these into Google Antigravity's multi-million token conversation stream to prevent false-positive `429 RESOURCE_EXHAUSTED` gateway errors.

---

### 2. Cursor IDE
1. Open Cursor Settings (**Ctrl+,** or **Cmd+,**).
2. Go to **Features** &gt; **Models**.
3. Under **OpenAI API Key**, enter: `prime-gate-proxy`.
4. Toggle on **Override OpenAI Base URL** and enter:
   ```text
   http://127.0.0.1:52111/v1
   ```
5. In **Add Model**, add your desired models:
   - `claude-sonnet-4-6` (Thinking enabled)
   - `gemini-3.8-flash` (Recommended daily driver)
   - `claude-opus-4-6-thinking`

---

### 3. OpenCode (`~/.config/opencode/opencode.json`)
Add or merge the `antigravity` provider in your OpenCode configuration:
```json
{
  "providers": {
    "antigravity": {
      "baseUrl": "http://127.0.0.1:52111/v1",
      "apiKey": "pg-live-your-key-here",
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

---

### 4. Continue.dev (`~/.continue/config.json`)
Add Prime Gate into your `models` list:
```json
{
  "models": [
    {
      "title": "Claude Sonnet 4.6 (Prime Gate)",
      "provider": "openai",
      "model": "claude-sonnet-4-6",
      "apiBase": "http://127.0.0.1:52111/v1",
      "apiKey": "pg-live-your-key-here"
    },
    {
      "title": "Gemini 3.8 Flash (Prime Gate)",
      "provider": "openai",
      "model": "gemini-3.8-flash",
      "apiBase": "http://127.0.0.1:52111/v1",
      "apiKey": "pg-live-your-key-here"
    }
  ]
}
```

---

### 5. Cline / Roo Code (VS Code Extension)
1. Open Cline Settings.
2. Select API Provider: **OpenAI Compatible** (or **Anthropic** at `http://127.0.0.1:52111`).
3. Set **Base URL**: `http://127.0.0.1:52111/v1` (or `http://127.0.0.1:52111` for Anthropic).
4. Set **API Key**: `prime-gate-proxy`.
5. Set **Model ID**: `claude-sonnet-4-6` or `gemini-3.8-flash`.

---

### 6. Aider (Terminal AI Pair Programmer)
Launch Aider pointing to the Prime Gate proxy endpoint:
```bash
aider --openai-api-base http://127.0.0.1:52111/v1 \
      --openai-api-key prime-gate-proxy \
      --model openai/claude-sonnet-4-6
```

---

### 7. Python OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:52111/v1",
    api_key="prime-gate-proxy"
)

# Streaming with reasoning / thinking
response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[
        {"role": "user", "content": "Write an optimized LRU cache with threading lock."}
    ],
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    # Thinking stream
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(f"[THINKING] {delta.reasoning_content}", end="", flush=True)
    # Output content stream
    if delta.content:
        print(delta.content, end="", flush=True)
```

---

### 8. Node.js / TypeScript SDK
```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:52111/v1",
  apiKey: "prime-gate-proxy",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "gemini-3.8-flash",
    messages: [{ role: "user", content: "Explain SQLite WAL mode in 3 sentences." }],
  });

  console.log(completion.choices[0].message.content);
}

main();
```

---

### 9. cURL / REST API Test
```bash
curl -X POST http://127.0.0.1:52111/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer pg-live-your-key-here" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Hello Prime Gate!"}],
    "stream": false
  }'
```

---

### 10. Health & Observability API (`/v1/health`)
Query gateway status, operational health for all models, quota buckets, and recent structured logs:
```bash
# Basic health check
curl http://127.0.0.1:52111/v1/health

# Health check with last 20 logs filtered by ERROR level
curl "http://127.0.0.1:52111/v1/health?limit=20&level=ERROR"

# Health check with force live refresh from upstream Antigravity
curl "http://127.0.0.1:52111/v1/health?refresh=true"
```

---

## 🧠 Real-Time Reasoning & Thinking Stream

For models with extended thinking capabilities (**Claude Sonnet 4.6**, **Claude Opus 4.6**, and **Gemini 3.8 Flash**), Prime Gate parses Google Antigravity's internal reasoning events and streams them via standard OpenAI delta chunks:

```json
{
  "choices": [
    {
      "index": 0,
      "delta": {
        "reasoning_content": "Deconstructing problem into fundamental constraints..."
      }
    }
  ]
}
```

- **In Web UI Sandbox:** Thinking blocks are rendered within glowing `[THINKING] ... [/THINKING]` badges before the final response stream.
- **In Compatible IDEs (Cursor/OpenCode):** Thinking thoughts appear natively in collapsible thought boxes.

---

## 🛡️ SQLite WAL Database & Sentinel Integrity Watchdog

Unlike traditional proxies that store OAuth tokens and credentials in unencrypted `accounts.json` files, Prime Gate uses an **SQLite database in Write-Ahead-Logging (WAL) mode** (`data/prime_gate.pgdb`):

- **Binary Record Obfuscation:** Sensitive tokens and quotas are obfuscated in binary BLOB records (`REC_ACCOUNT`, `REC_MODEL`, `REC_QUOTA`) to prevent plaintext leakage on disk.
- **32-Bit CRC32 Integrity Checksums:** Every binary block includes a 32-bit CRC32 checksum for storage corruption detection. If corruption occurs, Sentinel Watchdog alerts the user.
- **SQLite WAL Mode:** Supports ultra-low latency, concurrent reads and writes without file-locking bottlenecks.
- **WebSocket Event Bus (`/ws/live`):** Live database mutations and error logs are broadcast in real-time to the Web UI dashboard terminal.

---

## 📊 Subscription Tier Catalog & Quota

Prime Gate queries Google's internal APIs dynamically to detect your account's exact tier:

| Model Name | Google AI Pro (Trial Tier) | Google AI Pro (Paid Tier) | Thinking Support |
| :--- | :---: | :---: | :---: |
| **Claude Sonnet 4.6 (Thinking)** | ✅ Available | ❌ Replaced by 5.5 | ✓ Up to 64k tokens |
| **Claude Opus 4.6 (Thinking)** | ✅ Available | ❌ Replaced by 5.5 | ✓ Deep reasoning |
| **Gemini 3.8 Flash** | ✅ Available | ✅ Available | ✓ Fast thinking |
| **Gemini 3.8 Flash High / Med / Low** | ✅ Available | ✅ Available | ✓ Configurable budget |
| **Gemini 3.1 Flash Lite** | ✅ Available | ✅ Available | Standard |
| **GPT-OSS 120B (Medium)** | ✅ Available | ✅ Available | Standard |
| **Claude Sonnet 5.5 (Thinking)** | ❌ Paid Exclusive | ✅ Available | ✓ Extended thinking |
| **Gemini 4 Argon (Low)** | ❌ Paid Exclusive | ✅ Available | Standard |

> ⚠️ **Notice on Gemini 2.5:** `gemini-2.5-pro` and `gemini-2.5-flash` were removed from the active catalog due to Google upstream 503 capacity exhaustion (`MODEL_CAPACITY_EXHAUSTED`). Please use **`gemini-3.8-flash`** or **`claude-sonnet-4-6`**.

---

## 🧠 Next-Gen Smart & Semantic Vector Caching (Hybrid Engine)

Prime Gate features an enterprise-grade **Hybrid Caching Engine** that combines zero-millisecond exact SHA-256 matching with local CPU-driven vector semantic search, solving the classic 100% cache-miss problem on AI coding assistants:

```mermaid
graph TD
    Request["Incoming Request (OpenAI / Anthropic)"]
    --> Extract["Context-Key & Scope Extraction (API Key / Project / System / History / Files)"]
    
    Extract --> StepA{"Step A: Exact SHA-256 Hash Hit?"}
    StepA -->|"Found (0ms)"| ExactHit["Exact Cache Hit (~2ms TTFT)<br/>X-Cache: HIT (EXACT)"]
    
    StepA -->|"Miss"| StepB{"Semantic Vector Engine Enabled?"}
    StepB -->|"No"| Upstream["Upstream Google Antigravity"]
    
    StepB -->|"Yes"| ContextCheck{"Context Hash Match?"}
    ContextCheck -->|"Diff Context / Files"| Upstream
    
    ContextCheck -->|"Same Context"| FastEmbed["Multilingual FastEmbed ONNX<br/>(paraphrase-multilingual-MiniLM / multilingual-e5)"]
    FastEmbed --> Vector["Compute 384-dim Query Vector (with E5 prefix if applicable)"]
    Vector --> Cosine["In-Memory Scope-Isolated Cosine Scan"]
    
    Cosine --> Check{"Score >= Threshold (Chat: 0.93 / Agent: 0.96)?"}
    Check -->|"Yes"| SemanticHit["Semantic Cache Hit (~12ms TTFT)<br/>X-Cache: HIT (SEMANTIC)"]
    Check -->|"No"| Upstream
    
    Upstream --> Stream["Stream Tokens to Client"]
    Stream --> Save{"Active Tool Calls or Error?"}
    Save -->|"No (Clean Text Output)"| Store["Persist Passage Vector, TTL & LRU in SQLite WAL"]
    Save -->|"Yes (tool_use / error)"| Skip["Bypass Cache Storage"]
```

### ⚡ Key Capabilities:
1. **Multilingual Embedding Accuracy (Indonesian Paraphrase Optimization):** Powered by `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (or `intfloat/multilingual-e5-small`) via FastEmbed CPU ONNX Runtime (~100MB RAM, zero PyTorch/CUDA). Tested to achieve $\ge 0.93$ (0.978 empirical) similarity on Indonesian colloquial paraphrases while properly prefixing E5 queries/passages.
2. **Context-Aware Cache Key (Anti-Hallucination Isolation):** Generates tuple keys `(scope, context_hash, last_user_query, query_hash, tools_sig, has_tools)`. The `context_hash` digests system prompts, full conversation history, referenced file contents, and generation settings (`model`, `temperature`). Two identical questions referencing different source code will **never hit** the cache.
3. **Multi-Tenant Scope Isolation:** Partitions cached vectors per API key prefix (`key_<prefix>`) and per session/project identifier (`project_id`), strictly preventing cross-user cache contamination.
4. **Strict Coding Agent Policy:** Separates tool declaration from execution. Agent requests default to exact matching; semantic matching for agent turns is opt-in with a heightened threshold (0.96). Responses containing `tool_use` / `tool_calls`, streaming errors, or partial chunks are never cached.
5. **Configurable TTL & Automatic LRU Eviction:** Manages cache lifecycle with customizable TTL (default 24 hours), maximum entry capacity (default 5,000 entries), and Least-Recently-Used eviction. Automatically purges/rebuilds vector indexes if embedding model or dimensions change.
6. **Industry Standard Audit Headers:** Every response provides diagnostic headers:
   - `X-Cache: HIT | MISS`
   - `X-Cache-Type: EXACT | SEMANTIC | NONE`
   - `X-Cache-Similarity: <0.0000 - 1.0000>`
   - `X-Cache-Key-Scope: <scope_id>`
7. **Verification Sampling & False-Hit Rate Radar:** Background sampling ledger (`pg_cache_verifications`) continuously measures cache fidelity against upstream outputs to report empirical false-hit rates on the Web UI.
8. **Smooth Chunked SSE Replay & Upstream Prefix Caching:** Replays cached streaming responses in 4-word / 3ms micro-sleep chunks for realistic IDE animations, with alphabetically sorted function declarations to maximize Google Antigravity prefix cache reuse.

---

## ❓ FAQ & Troubleshooting

### 1. "503 Service Unavailable: MODEL_CAPACITY_EXHAUSTED"
- **Cause:** Requesting older or heavily congested models like Gemini 2.5.
- **Fix:** Use `gemini-3.8-flash` or `claude-sonnet-4-6`.

### 2. "Errno 10048: Only one usage of each socket address is normally permitted"
- **Cause:** Port 52111 or 52110 is already being used by an existing background process.
- **Fix:** Stop existing daemons via `prime-gate daemon stop`, or pass a custom port: `prime-gate start --port 52120`.

### 3. "Where are credentials saved?"
- **Answer:** In `data/prime_gate.pgdb` (compiled binary database). It is automatically ignored by Git, ensuring **zero credentials or tokens are committed**.

---

## 📁 Repository Structure

```text
prime-gate-proxy-antigravity-lik/
├── bin/                       # Windows CMD & Node.js CLI launchers
├── locales/                   # Multi-language documentation (ID, ZH, RU, JA, DE, FR)
├── prime_gate/                # Python Core Engine Package
│   ├── auth/                  # OAuth & Multi-Account Managers
│   ├── daemon/                # Windows Headless Background Service
│   ├── quota/                 # Dynamic Quota & Subscription Tier Resolver
│   ├── translator/            # OpenAI & Anthropic <-> Antigravity Converters
│   ├── cli.py                 # Rich Terminal CLI Interface
│   ├── config.py              # Ports, Credentials & Runtime Settings
│   └── server.py              # FastAPI OpenAI & Anthropic Compatible Endpoints
├── scripts/                   # One-Click Windows Batches (install, start, stop)
├── ui/                        # Node.js Web UI Dashboard
│   ├── public/                # Glassmorphic Static Assets (HTML/CSS/JS)
│   └── server.js              # Ultra-lightweight Native HTTP Proxy Server
├── package.json               # Node.js Project Metadata
├── pyproject.toml             # Python PEP 517/621 Metadata
├── requirements.txt           # Python Dependencies
├── README.md                  # Main English Documentation
└── LICENSE                    # MIT License
```

---

## 🤝 Contributing

Contributions, bug reports, and feature pull requests are warmly welcome!
1. Fork this repository.
2. Create your feature branch (`git checkout -b feature/amazing-feature`).
3. Commit your changes (`git commit -m 'feat: add amazing feature'`).
4. Push to the branch (`git push origin feature/amazing-feature`).
5. Open a Pull Request.

---

## 📜 License & Author

- **Author:** [Irham Karaman](https://github.com/irhamkaraman)
- **License:** Distributed under the [MIT License](LICENSE).

<div align="center">
<b>Built with ❤️ for the Global AI & Open-Source Developer Community.</b>
</div>


---

## 🔒 Security Architecture & Migration Guide

Prime Gate v1.2.4 implements comprehensive enterprise-grade security hardening to protect credentials, local traffic, and proxy integrity:

### 1. Credentials Encryption At-Rest (AES-256-GCM)
- **Industry-Standard Cryptography:** OAuth credentials, refresh tokens, and session states are encrypted using **AES-256-GCM** authenticated encryption (`cryptography` library) with a unique 12-byte random nonce per record and Additional Authenticated Data (AAD) bound to the record key.
- **Master Key Isolation:** The 256-bit master encryption key is securely stored in the hardware-backed **OS Keyring** (`keyring`):
  - Windows: DPAPI (Data Protection API)
  - macOS: Keychain
  - Linux: SecretService / libsecret
  - *Protected Fallback:* If an OS Keyring is unavailable, the system derives an encryption key via **Scrypt KDF** using a locally stored salt, accompanied by explicit security warnings.
- **Layered Integrity:** A 32-bit CRC32 checksum provides physical storage verification (*bit-rot detection*), while tampering detection and authenticity are guaranteed by the AES-GCM authentication tag.
- **Key Rotation:** Administrators can rotate the master encryption key at any time:
  ```bash
  python -m prime_gate.cli db rotate-key
  ```

### 2. Mandatory Authentication & API Key Policy Enforcement
- **Proxy Endpoint Protection:** All requests to `/v1/chat/completions`, `/v1/messages`, `/v1/messages/count_tokens`, and `/v1/models` require a valid API Key via standard headers:
  ```http
  Authorization: Bearer pg-live-...
  # or
  x-api-key: pg-live-...
  ```
- **Secure Key Storage:** Raw API keys (`pg-live-<32 hex chars>`) are displayed **only once** upon generation and are never stored in plaintext. The database retains only a **salted SHA-256** hash.
- **Constant-Time Verification:** Key hashes are verified using constant-time string comparison (`hmac.compare_digest`) to neutralize timing attacks.
- **Rate Limiting & Token Quotas (RPM / TPD):** Sliding-window rate limiting per minute (RPM) and token quotas per day (TPD) are strictly enforced per key. Exceeding limits returns a standard HTTP 429 response with a `Retry-After: <seconds>` header.
- **Dynamic Model Whitelisting:** Each API key can restrict access to a specific list of models. Requests for unauthorized models are blocked with HTTP 403 Forbidden.
- **Cache Scope Isolation:** Cache entries are isolated per key (`global` or `scoped:<key_id>`), ensuring strict multi-tenant privacy.
- **Rate-Limiting on Failed Attempts:** Failed authentication attempts are rate-limited to a maximum of 5 failures per 5 minutes per IP. Exceeding this triggers a 5-minute lockout (`HTTP 429 Too Many Requests`).
- **Non-Loopback Bind Guard:** Binding the proxy to non-loopback interfaces (`0.0.0.0` or public IPs) is blocked by default unless API Key authentication is actively configured.

### 3. Dashboard Protection Against Localhost Attacks
- **DNS Rebinding Mitigation:** `HostValidationMiddleware` inspects the `Host` header on every incoming request. Requests with untrusted host headers (e.g., external domains resolving to `127.0.0.1`) are immediately rejected with `HTTP 403 Forbidden`.
- **Strict Origin Validation:** State-mutating requests (`POST`, `PUT`, `DELETE`) are strictly validated to originate from the authorized local dashboard.
- **Double-Submit CSRF Protection:** The dashboard leverages a `pg_csrf` cookie matched against the `x-csrf-token` header on all mutation calls.
- **Comprehensive Security Headers:** Responses include modern protective headers:
  - `Content-Security-Policy: default-src 'self'; ...`
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: strict-origin-when-cross-origin`
- **Authenticated WebSocket Handshake:** The `/sentinel` WebSocket endpoint validates the `pg_session` cookie and origin before granting real-time auditing access.

### 4. Safe Auto-Update (Zero-Touch Verification)
- **Tagged Release Verification:** Updates are fetched systematically from the GitHub Releases API based on official release tags rather than unvetted branch pulls.
- **SHA-256 Integrity Validation:** Release packages are verified against SHA-256 checksums before applying updates.
- **Default "Notify Only":** Auto-update defaults to *notify only* (`auto_apply: False`), giving users full agency over updates.
- **Safety Gate & Automatic Rollback:** Updates are executed only when the system is idle (0 in-flight requests and zero traffic for $\ge 30$ seconds). If post-update health checks fail, the system automatically rolls back to the prior snapshot.
- **Zero Shell Injection:** Network input is never passed to arbitrary shell executors (`shell=False`).

### 5. Centralized Log Redaction
- A centralized regex scrubber (`prime_gate.logging.redactor`) filters Google OAuth tokens, refresh tokens, Bearer headers, session cookies, and API keys from console logs, log files, WebSocket audit streams, and HTTP error bodies.

### 6. Database Migration Guide (V1 -> V2)
For users upgrading from earlier releases:
1. **Automatic Migration:** On startup, Prime Gate v1.2.4 detects legacy V1 database records (XOR obfuscation), creates an automatic snapshot in `data/backups/backup_pre_v2_<timestamp>.pgdb`, and idempotently migrates records to V2 AES-256-GCM.
2. **Initial Key Generation:** If no API key exists, a default initial key is automatically generated and displayed in the terminal during startup.
3. **Manual Rollback:** In case of database anomalies, roll back anytime via:
   ```bash
   python -m prime_gate.cli db rollback
   ```
