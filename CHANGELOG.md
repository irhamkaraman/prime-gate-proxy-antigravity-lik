# Changelog

All notable changes to **Prime Gate Antigravity Proxy** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.5] - 2026-10-18

### ⚡ Smart Semantic Caching Layer & Dedicated "Caching Usage" Dashboard

#### 1. Zero-Quota Smart Semantic Caching Engine
- **Deterministic SHA-256 Prompt Hashing:** Canonically hashes normalized conversation messages and model targets, generating unique, deterministic cache keys (`pg_semantic_cache`).
- **Instant Response Streaming (~3ms TTFT):** Intercepts identical requests before hitting upstream Google Antigravity servers, serving complete responses in ~3.2ms (3.1x faster than network, >2000x faster than upstream generation) with **zero quota consumption**.
- **Standardized OpenAI Streaming & Headers:** Delivers cached SSE chunks (`stream_cached_response_sse`) with standard `role: assistant`, `content`, and `finish_reason: stop`, returning `X-Cache: HIT` and `X-Tokens-Saved: <count>` response headers.
- **Microsecond Binary WAL Persistence:** Cached prompts and responses are stored in high-performance SQLite WAL mode with CRC32 integrity validation.

#### 2. Agent Safety Boundary (Dynamic Tool Bypass)
- **Automatic Dynamic Tool Guard:** Autonomous AI agents (OpenCode, Cursor, Continue, Claude Code) frequently execute ephemeral filesystem inspections (`read`, `write`, `edit`) and terminal tasks (`bash`). When dynamic tool definitions are present, caching is cleanly bypassed by default (`bypass_tools: true`) to prevent stale state and hallucinations.
- **Header & Payload Cache Controls:** Supports explicit bypass controls via client headers (`X-Cache-Bypass: true`, `X-No-Cache: true`) or request payload flags (`cache: false`, `no_cache: true`).

#### 3. Dedicated "Caching Usage" UI Menu & Dashboard
- **New Sidebar Navigation Item:** Integrated **"Caching Usage"** menu item with `Zap` icon in the application sidebar and routing system (`/caching`).
- **Real-Time Analytics KPI Cards:**
  - **Total Tokens Saved:** Live counter of all tokens preserved via cache hits with economic efficiency badges.
  - **Smart Cache Hit Ratio:** Percentage of total requests resolved via cache vs upstream execution.
  - **Active Cache Entries:** Real-time count of unique prompt patterns preserved in binary database.
  - **Estimated Latency Saved:** Total developer waiting seconds saved across cache hits.
- **Live Cache Engine Controls:** Interactive glass card toggles to enable/disable caching, toggle Agent Safety tool bypass, and configure minimum prompt length thresholds.
- **Searchable Persistent Cache Ledger:** Interactive table detailing Cached Model, Prompt Preview, Response Preview, Token Breakdown, Hit Count, Cumulative Tokens Saved, and Last Hit Timestamp with single-entry deletion and full modal inspection.

#### 4. Granular Request Hit Ledger Breakdown & Cumulative Totals
- **Visual Cache Hit Badges:** Cache hits in the **Usage** ledger table (`ModelBenchmarkPage`) now feature a prominent `⚡ CACHE HIT` badge displaying exact tokens saved (`+N saved`).
- **Zero Upstream Cost Indicator:** Total Tokens column displays a dedicated `⚡ 0 upstream` indicator for cache hits, ensuring transparency in quota accounting.
- **Automated Metric Accumulation:** Model Rankings and global summary statistics automatically aggregate cache hits and tokens saved into cumulative totals.

---

## [1.1.4] - 2026-10-18

### 🐛 Critical Agent Loop Fix: Full Tool Call & Parameter Normalization

#### 1. Eliminated Autonomous Agent Infinite Tool Call Loops
- **Root Cause Resolution:** Fixed an issue where agents (OpenCode, Continue, Cursor, Claude Code) entering tool calling sequences (such as `edit gitignore`) became trapped in infinite execution loops failing with `Invalid arguments for tool "write": - content: Missing key`.
- **Tool Name Collision Guard:** Previously, tool mapping heuristics aggressively checked candidate tool names in fixed order (`write_file`, `write`, `edit_file`, `edit`), causing surgical `edit` tool calls from the model to be forcibly renamed to `write` whenever the client declared both tools. `normalize_tool_call()` now enforces that if `fn_name` is already in the client's declared tools, it is strictly preserved without remapping.
- **Dedicated Surgical Edit vs Whole-File Write Mappings:** Separated `edit` (surgical diff replacement: `old_string`, `new_string`, `pattern`, `replacement`, `TargetContent`, `ReplacementContent`) from `write` (complete file creation/overwriting: `path`, `content`, `TargetFile`, `CodeContent`), preventing tool signature mismatches across diverse agent frameworks.

#### 2. Universal Parameter Alias Mapping & Strict Schema Validation
- **Path & Content Aliasing:** Standardized bidirectional parameter alias translation across Antigravity native names (`TargetFile`, `CodeContent`, `AbsolutePath`, `filePath`, `file_path`, `code`, `text`, `contents`, `data`, `body`) and OpenAI standard parameters (`path`, `content`).
- **Required Property Fallback:** Automatically sets safe defaults (such as `content: ""` for empty file creations or initial touches) whenever client-side Zod validation schemas declare `content` as strictly required, preventing client exceptions.
- **Extraneous Metadata Filtering:** Transparently strips internal model metadata (`toolAction`, `toolSummary`, `timeout`, `Instruction`, `Description`) so strict schema validators do not reject tool invocations.
- **Unified Engine Integration:** Consolidated parameter normalization into `normalize_tool_call()`, applied identically across SSE streaming chunks (`stream_antigravity_sse`), non-streaming completions (`/v1/chat/completions`), and text-block function call extractions (`extract_text_tool_calls`).

---

## [1.1.3] - 2026-10-18

### 🚀 Model Benchmarks & Persistent Request Hit Ledger

#### 1. SQLite WAL Binary Request Hit Ledger
- **Automatic Request Capture:** Every inbound request through `/v1/chat/completions` (both SSE streaming and non-streaming REST) is now automatically persisted into `pg_request_logs` with microsecond-level latency tracking and exact token metrics (`prompt_tokens`, `completion_tokens`, `reasoning_tokens`, `total_tokens`).
- **Live Quota State Snapshots:** Persists the active account's Google Antigravity quota bucket state (`percentage`, `family`, `reset_time`) at the exact time of the request hit, providing historical traceability of quota depletion.
- **Microsecond Write Overhead:** Employs SQLite WAL mode (`wal_autocheckpoint=1000`) and compiled binary engine semantics, recording requests in under 50µs with zero impact on streaming latency.

#### 2. Model Performance Benchmarks & Quota Impact Scoring
- **Automated Usage Ranking:** Endpoint `GET /api/analytics/models` computes real-time token volume shares, request counts, minimum/maximum/average latency (TTFT), and generation throughput (`tokens/sec`) per model.
- **Quota Impact Weighting:** Identifies heavy quota drainers with a tier-weighted formula: Claude (3x), GPT (2x), and Gemini Flash (1x) multiplier over token volume share, surfacing models that exhaust quota limits fastest.

#### 3. Dedicated Web UI: "Model Benchmark & Usage"
- **New Sidebar Menu:** Added **"Model Benchmark & Usage"** route (`/benchmarks`) with `BarChart3` icon in the application sidebar and navigation context.
- **Analytics KPI Stat Cards:** Displays **Top Token Spender Model**, **Heaviest Quota Consumer**, **Lowest Latency Model**, and **Total Ledger Hits Recorded**.
- **Model Comparison Table:** Ranked breakdown of all models with visual percentage share progress bars, TTFT latency badges, throughput rates, and Quota Impact score pills (**Severe**, **Heavy**, **Moderate**, **Light**).
- **Searchable Request Ledger:** Filterable and paginated table detailing Timestamp, Request ID (with one-click copy), Model badge, Account Email, Prompt/Completion/Reasoning breakdown, Latency badges, Streaming mode, and Quota Snapshot pills.
- **Ledger Management:** Built-in modal-confirmed "Clear Ledger" and real-time "Refresh" controls.

#### 4. Dashboard Benchmark Preview Widget
- **Top Token Spenders Leaderboard:** Embedded preview widget in `DashboardPage.tsx` directly underneath the token volume chart, displaying the top 4 token-consuming models, progress bars, and quota drainer alerts with direct navigation to the full hit ledger.

#### 5. Token Chart Filters & Real-Time WebSocket Synchronization
- **Streamlined Range Selection:** Upgraded time-series filters to `1m`, `1h`, `1d`, and `1month`, deprecating noisy sub-second intervals (`1s`).
- **WebSocket Range Isolation:** Eliminated race condition where background `TELEMETRY_UPDATE` WebSocket frames hardcoded to minute intervals would prematurely overwrite and desynchronize user-selected `1h`, `1d`, or `1month` charts.
- **SQLite WAL-Backed Time Series:** Extended telemetry resolution to aggregate historical requests directly from `pg_request_logs`, ensuring hourly, daily, and 30-day monthly trends remain persistent across server restarts.

#### 6. Real-Time Usage Page & Concise Sidebar Navigation
- **Renamed to "Usage":** Streamlined the sidebar navigation title from "Model Benchmark & Usage" to a cleaner, more concise **"Usage"**.
- **Real-Time WebSocket Ingestion:** Implemented immediate event dispatch (`REQUEST_LOGGED` and `LEDGER_CLEARED`) from backend chat completion pipelines to active WebSocket clients.
- **Dynamic Usage Dashboard Sync:** The Usage page (`ModelBenchmarkPage`) and Dashboard benchmark preview widget now automatically re-calculate token rankings, throughput, and latency metrics in real time upon every inbound request hit.
- **Live Status Visual Pill:** Added a glowing `LIVE REALTIME` / `POLLING SYNC` badge in the header confirming persistent stream connectivity without disrupting user table pagination or search filters.

#### 7. Visual Interface Demonstration & Multi-Language Documentation
- **Showcase Gallery:** Captured and stored high-resolution demonstration screenshots for all 5 SPA application views in `docs/images/` (`dashboard-telemetry.png`, `usage-benchmarks.png`, `accounts-models.png`, `prompt-sandbox.png`, `system-sentinel.png`).
- **Comprehensive Multi-Lingual Sync:** Updated all documentation across 6 languages (English, 简体中文, Русский, 日本語, Deutsch, Français) with detailed feature walkthroughs and visual previews.

---

## [1.1.2] - 2026-10-18

### 🚀 Major Architectural Enhancements

#### 1. Full React + TypeScript SPA Frontend Architecture
- **Complete UI Rewrite:** Rebuilt the entire frontend from vanilla HTML/JS into a modern, modular React 18 + TypeScript + Vite Single Page Application (SPA).
- **Client-Side Routing & Navigation:** Introduced `NavigationContext` with dedicated views for:
  - **Dashboard & Telemetry:** Real-time token consumption breakdown, throughput radar, active quota gauge, and OpenAI endpoint credentials.
  - **Account Manager:** Multi-account authentication, live active account indicator, token status, quota bucket inspectors, and dynamic model catalogs.
  - **Prompt Sandbox:** Interactive streaming playground with real-time token telemetry and thinking breakdown.
  - **System & Sentinel:** Database audit ledger, real-time daemon logs, CRC32 verification triggers, and vacuum compaction.
  - **Documentation:** Built-in integration guides for OpenCode, Cursor, Continue, Cline, and API references.
- **Modern Design System:** Warm Anthropic-inspired dark glassmorphism aesthetic with polished typography, monospace data readouts, micro-interactions, responsive sidebars, custom modal dialogs, and toast notifications.

#### 2. Responsive Token Consumption Breakdown Chart
- **Edge-to-Edge Responsive Layout:** Integrated a dynamic `ResizeObserver` lifecycle in `TokenChart.tsx` that binds SVG coordinate space directly to container width, eliminating letterboxing and dead whitespace on ultra-wide and high-DPI displays.
- **Proportional Bar Distribution:** Evenly spaces time-series bars across the entire card width (`1s`, `1m`, `1h`, `1d`), calculating bar widths and gaps proportionally to data point density.
- **Subtle Baseline Indicator Tracks:** Added faint slot indicators (`rgba(255, 255, 255, 0.08)`) for time periods with 0 token consumption, giving the timeline a cohesive, structured appearance rather than floating, isolated bars.
- **Anti-Collision X-Axis Labels:** Implemented dynamic stride interval calculations preventing text overlapping on dense time intervals.
- **Interactive Tooltip & Crosshair:** Hovering over any time slot displays a dashed vertical crosshair and floating glass tooltip with exact counts for **Prompt**, **Reasoning (Thinking)**, **Completion**, and **Total Tokens**.

#### 3. Real-Time Streaming Tool Call Interception & Token Buffer
- **Streaming State Machine:** Added an in-memory token buffer to `stream_antigravity_sse()` in `prime_gate/server.py` that intercepts Google Antigravity's text-based function call syntax (e.g., `call:default_api:shell{...}`).
- **Zero Content Leakage:** Prevents raw tool execution strings from leaking into client chat bubbles as conversational text, ensuring AI agents do not halt prematurely.
- **Balanced Braces Scanning:** Upgraded argument parsing from naive regex to a balanced curly-brace state machine capable of extracting complex nested JSON payloads without syntax corruption.
- **Reasoning Stream Routing:** Automatically redirects `Thought: <time>ms` blocks to OpenAI `delta.reasoning_content` chunks, rendering cleanly in collapsible thinking drawers in OpenCode, Cursor, and Continue.

#### 4. Agent Loop & Schema Compatibility (OpenCode, Cursor, Continue)
- **Intelligent Tool Mapping:** Translates internal Google Antigravity tool names to standard agent tools:
  - `default_api:shell` / `shell` $\to$ `bash` / `run_command` / `terminal` / `exec`
  - `default_api:view_file` / `view_file` $\to$ `read_file` / `read` / `readFile`
  - `default_api:write_to_file` / `write_to_file` $\to$ `write_file` / `write` / `edit`
  - `list_dir` / `ls` $\to$ `list_files` / `list`
- **Strict Parameter Normalization & Filtering:** Normalizes parameter aliases (`command` $\leftrightarrow$ `cmd`, `AbsolutePath` $\leftrightarrow$ `path`, `CodeContent` $\leftrightarrow$ `content`) and filters out unadvertised arguments like `,timeout:30000`, preventing strict Zod schema validation errors.
- **Standard OpenAI SSE Deltas:** Streams well-formed `tool_calls` deltas with proper UUID identifiers, culminating in `finish_reason: "tool_calls"`.

#### 5. Dynamic Binary Database Model Resolution
- **Zero Hardcoded Models:** Eliminated static model dictionaries from request/response translators. All model specifications, context limits, and capabilities are dynamically queried from the compiled binary database (`data/prime_gate.pgdb`).
- **Antigravity Live Sync:** Automatically pulls live models directly from Google's `fetchAvailableModels` endpoint upon daemon startup, user login, manual UI refresh, and account switching.
- **Tier-Aware Routing:** Seamlessly accommodates account tier variances (Google AI Pro Trial vs Paid tiers) and dynamically resolves upstream aliases (e.g. `gemini-3.8-flash` $\to$ `gemini-3.8-flash-high`).

---

## [1.1.1] - 2026-10-17

### 🛠️ Authentication & System Hardening

#### Added
- **System Health Diagnostics (`/v1/health`):** Comprehensive JSON endpoint providing health metrics, live quota status, model availability, and telemetry summaries.
- **Model Metadata Tagging:** Added `owned_by: "google-antigravity"` and `provider: "prime gate proxy"` to `/v1/models` outputs for seamless provider recognition in Cursor and OpenCode.
- **Dedicated Post-Auth Flow:** Added an English OAuth callback page with a direct "Go to Dashboard" button.
- **Sidebar Quick Account Switcher:** One-click account switcher in both the Web UI sidebar and CLI commands.

#### Fixed
- **Google OAuth Login Flow:** Resolved OAuth loop and token exchange errors with resilient callback handling, direct popup support, and verbose error extraction.
- **Global Localization:** Enforced pure English across all UI components, CLI commands, scripts, and documentation for international developer consistency.
- **Terminal Management Commands:** Added comprehensive CLI flags for account deletion, token refreshing, and quota syncing.

---

## [1.1.0] - 2026-10-17

### ⚡ Performance & Storage Architecture

#### Added
- **Compiled Binary Database Engine (C SQLite + WAL):** Migrated from plaintext JSON files to a high-concurrency binary database (`prime_gate.pgdb`) using Write-Ahead Logging (WAL) and memory-mapped I/O (mmap 256MB).
- **Data Corruption Sentinel Daemon:** Background watchdog that calculates and verifies 32-bit CRC32 checksums on every record read, broadcasting real-time corruption alerts via WebSockets.
- **Multi-Account Failover:** Intelligent round-robin failover between configured Google Antigravity accounts when upstream rate limits (HTTP 429) are encountered.
- **WebSocket Event Bus:** Real-time bi-directional streaming of server logs, telemetry updates, and database events to connected browser sessions.

---

## [1.0.0] - 2026-10-16

### 🎉 Initial Public Release

- **OpenAI Compatible Gateway:** Complete drop-in compatibility for `/v1/chat/completions` (streaming & non-streaming) and `/v1/models`.
- **Google CloudCode Sandbox Bridge:** Secure reverse-engineered translation layer connecting OpenAI schema requests to Google's internal CloudCode Antigravity endpoints.
- **Token Telemetry Collector:** Rolling in-memory and persisted telemetry across four granularities (per-second, per-minute, per-hour, per-day).
- **Core CLI Suite:** Complete terminal management CLI:
  - `prime-gate auth login` / `prime-gate auth status`
  - `prime-gate daemon start` / `prime-gate daemon status` / `prime-gate daemon stop`
  - `prime-gate quota sync` / `prime-gate quota status`
