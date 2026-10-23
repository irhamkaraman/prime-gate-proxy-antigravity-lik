# 📸 Prime Gate UI & Dashboard Gallery

Welcome to the visual gallery of **Prime Gate Antigravity**. Prime Gate features an Anthropic-inspired dark glassmorphic web dashboard built with **React 18**, **TypeScript**, **Tailwind CSS v4**, and **High-Performance Bidirectional WebSockets**.

The Web UI is served natively on port `:52110` (or configured port) whenever the Prime Gate daemon is running.

---

### 1. Dashboard & Real-Time Telemetry (`/dashboard`)
Visualizes live token consumption, active throughput speed, rolling 24-hour token totals, average time-to-first-token (TTFT) latency, segmented token volume breakdowns (`1m`, `1h`, `1d`, `1month`), and a leaderboard preview of top token spenders and quota drainers.

![Dashboard & Telemetry](images/dashboard-telemetry.png)

---

### 2. Usage & Model Benchmarks (`/benchmarks`)
Persistent SQLite WAL-backed ledger recording every inbound API request hit in real time. Surfaces model analytics, latency benchmarks, token volume shares, and weighted Quota Impact scoring (Claude 3x, GPT 2x, Gemini 1x) with instant search, filtering, and copyable request IDs.

![Usage & Benchmarks](images/usage-benchmarks.png)

---

### 3. Account Manager & Dynamic Model Catalog (`/accounts`)
Multi-account OAuth management with active account rotation, quota depletion status, and automatic model catalog discovery with capability badges (Thinking Supported, Vision/Multimodal, Context Window, Streaming).

![Account Manager & Models](images/accounts-models.png)

---

### 4. Prompt Sandbox & Playground (`/sandbox`)
Interactive test bench for streaming model completions. Configure system prompts, user messages, temperature, and token budgets with real-time inference telemetry (TTFT, total generation time, tokens per second).

![Prompt Sandbox](images/prompt-sandbox.png)

---

### 5. System & Database Sentinel (`/sentinel`)
Auditing console for high-speed binary SQLite storage in WAL mode. Inspects header CRC32 integrity, page cache allocation, database vacuuming, and live daemon background audit logs over bidirectional WebSockets.

![System Sentinel](images/system-sentinel.png)

---

[⬅️ Back to README](../README.md)
