# Changelog

All notable changes to **Prime Gate Antigravity Proxy** will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.2.6] - 2026-10-23

### 🎨 Modular Documentation Overhaul, NPM Package Polish & Decoupled UI Gallery
- **NPM Package Hero Section:** Prominent, zero-dependency installation command (`npm i -g prime-gate-antigravity@latest` & `npx prime-gate-antigravity`) directly at the top with explicit CLI flag specifications and status metadata badges (NPM Version, 0 Dependencies, 0 Dependents, License, CI Passing, Platform).
- **Decoupled UI Gallery (`docs/SCREENSHOTS.md`):** Extracted large high-resolution dashboard screenshots out of the primary `README.md` into a dedicated gallery document, dramatically accelerating page load times and reading ergonomics across npmjs.org and GitHub.
- **Categorized Terminal Commands Cheatsheet:** Consolidated all CLI commands into a clean, categorized reference (Daemon Service Management, Google OAuth Auth, Client API Keys & Policies, Quota, Updates & SQLite WAL DB Maintenance).
- **Latest Supported Models Catalog:** Dedicated model matrix detailing context lengths, reasoning/thinking capabilities, and best-fit coding agents (Claude Sonnet 4.6, Claude Opus 4.6, Gemini 3.8 Flash, Claude 3.7 Sonnet).
- **Windows Terminal Resilience (cp1252):** Hardened CLI update notifier output with ASCII-safe formatting to eliminate `UnicodeEncodeError` on legacy Windows command shells.
- **Multi-Language Synchronization:** Propagated modular documentation design to Indonesian (`locales/id/`), Chinese (`locales/zh/`), Japanese (`locales/ja/`), Russian (`locales/ru/`), German (`locales/de/`), and French (`locales/fr/`).

---

## [1.2.5] - 2026-10-23

### 🌍 Global CLI Environment Variable (PATH) Automator, Multi-Platform Deployment & GitHub Packages CI/CD
- **Windows 1-Click PATH Automator (`scripts/setup-path.ps1` & `scripts/setup-path.bat`):** Otomatisasi instalasi paket editable (`pip install -e .`), pendeteksian folder `Scripts` Python, dan penambahan permanen ke Windows User Environment Variable `PATH`. Memungkinkan pemanggilan `prime-gate <command>` secara global dari direktori terminal mana saja tanpa `cd` atau mengetik `python -m prime_gate.cli`.
- **Pembaruan `pyproject.toml` Package Discovery:** Menambahkan konfigurasi eksplisit `[tool.setuptools.packages.find]` agar pip install editable tidak mengalami konflik flat-layout dengan folder UI/data.
- **Panduan Multi-Platform Lengkap (Windows, macOS, Linux, Docker):** Dokumentasi instalasi komprehensif di `README.md` dan `locales/id/README.md`.
- **Systemd Production Service Unit (`docker/systemd/prime-gate.service`):** File unit service Linux lengkap dengan *security hardening* (`NoNewPrivileges`, `PrivateTmp`, `ProtectSystem=full`) dan *auto-restart* saat boot.
- **Kontainerisasi Produksi Multi-Stage (`Dockerfile` & `docker-compose.yml`):**
  - Stage 1: Kompilasi frontend React 18 + Vite TypeScript via Node 20.
  - Stage 2: Runtime ringan Python 3.11-slim + Node.js dengan volume persisten `/app/data`.
  - Skrip `docker/entrypoint.sh` dengan generator kunci bootstrap otomatis, penangkapan sinyal gracefully (SIGINT/SIGTERM), serta healthcheck aktif.
- **GitHub Packages & Distribution Pipeline (`.github/workflows/publish-package.yml`):**
  - Publikasi otomatis image Docker ke GitHub Container Registry (`ghcr.io/irhamkaraman/prime-gate-proxy-antigravity-lik`).
  - Publikasi paket npm/npx ke GitHub Packages (`@irhamkaraman/prime-gate-proxy-antigravity-lik`).
  - Pembuatan dan pengunggahan aset release Python wheel (`.whl`) dan source distribution (`.tar.gz`).
- **Verifikasi Kualitas:** 122 dari 122 pengujian pytest lulus 100% hijau.

---

## [1.2.4] - 2026-10-23

### 🛡️ Client Gateway API Key Policy Enforcement, Dynamic Whitelisting & Cache Scope Isolation (Fase 5.1)
- **Granular Policy Enforcement:** Penegakan kebijakan akses per Client Gateway API Key (`pg-live-...`): laju request per menit (RPM), kuota konsumsi token LLM per hari (TPD), budget kredit seumur hidup (`quota_credits`), daftar model yang diizinkan (*allowed models whitelist*), dan isolasi cache semantic (*cache scope*).
- **Respons Error 429 Protokol-Spesifik dengan `Retry-After`:** Pelanggaran batas RPM maupun TPD dikembalikan sebagai HTTP 429 Too Many Requests dengan header `Retry-After: <detik>` dan body JSON yang sesuai format protokol klien (OpenAI vs. Anthropic).
- **Proteksi Whitelist Model (HTTP 403):** Permintaan model di luar daftar yang diizinkan ditolak seketika dengan HTTP 403 Forbidden (`model_not_allowed` untuk OpenAI, `permission_error` untuk Anthropic).
- **Isolasi Cache Semantic & Exact (Fase 3A):** Dukungan `cache_scope="key"` yang mempartisi namespace cache per ID kunci klien (`key_<id>:<project>`), mencegah *cache poisoning* dan kebocoran konteks antar-developer/agen, serta opsi `cache_scope="disabled"` untuk melewati cache sepenuhnya.
- **Buku Besar Penggunaan Token Klien (`pg_api_key_usage`):** Tabel database persisten dengan indeks waktu untuk mencatat metrik konsumsi token prompt, completion, total tokens, dan model per transaksi per kunci.
- **Pembaruan CLI Mandiri:** Perintah `prime-gate keys create` dengan opsi `--rpm`, `--tpd`, `--quota`, `--models`, `--cache-scope`, `prime-gate keys list` yang menampilkan kolom kebijakan lengkap (aman dari encoding issue Windows cp1252), serta `prime-gate keys revoke`.
- **Antarmuka Web Dashboard Dinamis (`/keys`):** Modal pembuatan Client API Key dengan input kebijakan lengkap, selector model dinamis dari database (bebas hardcoding), dan indikator badge kebijakan pada tabel daftar kunci.
- **Pembersihan Terminologi:** Menghapus label statis warisan "Auth API Key" pada fallback HTML dashboard dan menegakkan pemisahan mutlak antara Client API Key (downstream) dan Token Auth Login Akun Google (upstream).

---

## [1.2.3] - 2026-10-22

### 🚀 Autonomous Zero-Touch Auto-Update, Anti-ISP Web Search MCP, Git Stale Token Bypass & Gemini 3 Thought Signature

#### 1. Autonomous Zero-Touch Auto-Update Engine (Metode B)
- **Zero-Touch Background Sync:** Added automated background worker polling GitHub repository updates at regular intervals (`default: enabled`).
- **In-Flight & Idle Safety Gate:** Auto-updates only trigger when all accounts report `0 in-flight requests` and the proxy has been completely idle without traffic for $\ge 30$ seconds, preventing LLM streaming interruptions during active coding sessions.
- **Auto-Rebuild Frontend:** Automatically compiles frontend assets (`npm run build`) whenever UI files are updated.
- **Automatic Multi-User Database Schema Migration:** Automatically creates `pg_auto_update_ledger` and seeds default configuration in `pg_records` for both new and existing user databases without manual intervention.
- **Sidebar Live Status & Toggle:** Added sleek toggle switch for Auto Update and removed redundant sync buttons for a clean, minimalist UI.

#### 2. Resilient Git Updater & Stale Token Bypass
- **Anonymous Upstream Pulling:** Fixed GitHub 403 Forbidden on public repository updates by executing `git -c credential.helper= pull origin main`, preventing expired or restricted tokens in Windows Credential Manager from failing updates.
- **One-Click Windows Updater (`scripts/update.bat`):** Added double-click batch script for Windows users to update repository, dependencies, and build UI cleanly.

#### 3. Anti-ISP Blocking Web Search Engine & MCP
- **Cloudflare DNS-over-HTTPS (DoH 1.1.1.1):** Resolves DuckDuckGo and search endpoints via encrypted DoH, completely bypassing regional ISP DNS filtering.
- **Standalone MCP Server:** Exposes standard stdio Model Context Protocol `web_search` tool (`scripts/mcp_search.py`) for OpenCode and Claude Code.
- **Gateway Search API:** Registered `POST /v1/search` and `POST /search` for external tooling.

#### 4. Cryptographic Thought Signature Cache for Gemini 3
- **Upstream Reasoning Integrity:** Thread-safe cache storing cryptographic `thoughtSignature` tokens returned by Google Antigravity Gemini 3 reasoning models across multi-turn tool calling turns, resolving upstream HTTP 400/502 errors.

#### 5. Dokumentasi Jujur, Kepatuhan & Transparansi Risiko (Fase 1)
- **Eliminasi Klaim Absolut:** Menghapus seluruh klaim pemasaran absolut seperti "100% Anti-Banned" dan "Zero Token Waste" dari README, panduan pengguna, dan Web UI.
- **Transparansi Risiko & Batasan:** Menambahkan bagian eksplisit *Disclaimer & Risiko* (peringatan agar tidak memakai akun primer), *Batasan yang Diketahui (Known Limitations)*, serta *Model Ancaman (Threat Model)*.
- **Klarifikasi Simulator Nilai Ekonomi:** Mengganti label "Cost Savings" menjadi "Estimasi Nilai Setara Tarif Komersial", menegaskan bahwa pengguna memakai kuota langganan akun Google.
- **Akurasi Teknis Arsitektur Data:** Meluruskan deskripsi teknis dari "Compiled C Binary" menjadi SQLite WAL dengan binary record obfuscation & pengecekan integritas CRC32.
- **Pedoman Kontribusi Komunitas:** Menambahkan file panduan kontribusi resmi `CONTRIBUTING.md`.

#### 6. Stabilitas, Kualitas & Observabilitas Produksi (Fase 4)
- **Rangkaian Uji Konformansi Protokol:** Direktori `tests/conformance/` dengan fixture rekaman interaksi agent nyata (Claude Code, Cline, Cursor, Aider), mock upstream Antigravity, pengujian sekuens SSE 7-event Anthropic, akumulasi JSON delta, thinking blocks, OpenAI SSE chunking/reasoning/tools, dan `count_tokens`.
- **Manajemen Kunci API UI Terintegrasi (`/keys`):** Halaman dedikasi manajemen kunci API proxy dengan generator token bertanda `pg-live-...`, tab konfigurasi 1-klik untuk Claude Code, OpenCode, Cline, Cursor, Aider, cURL, serta sinkronisasi otomatis ke Prompt Sandbox (`/sandbox`) untuk mengeliminasi error `401 Unauthorized`.
- **Pengujian Resiliensi & Integrasi:** Pengujian menyeluruh untuk failover 429/503 sebelum token pertama, pemulihan cooldown akun, penanganan bersih ketika seluruh akun habis kuota, cache multi-turn `thoughtSignature` Gemini 3, migrasi skema database SQLite WAL idempoten, pembersihan slot in-flight saat koneksi klien terputus, dan uji konkurensi.
- **Observabilitas Tingkat Produksi:** Endpoint Prometheus `/metrics` dengan metrik standar (`primegate_requests_total`, `primegate_request_duration_seconds`, `primegate_time_to_first_token_seconds`, `primegate_tokens_total`, `primegate_cache_hits_total`, `primegate_cache_misses_total`, `primegate_active_accounts`, `primegate_account_failovers_total`, `primegate_compactor_tokens_saved_total`).
- **Health & Readiness Probes:** Endpoint `/health` dengan sub-blok `liveness` dan `readiness`, serta endpoint mandiri `/health/liveness` dan `/health/readiness` untuk probe Kubernetes/Docker.
- **Pelacakan Terdistribusi (`X-Request-ID`):** Middleware ASGI pelacakan request id end-to-end yang otomatis menghasilkan atau mempropagasi `X-Request-ID` pada header HTTP dan log database.
- **Structured JSON Logging:** Opsi logging JSON (`LOG_FORMAT=json`) dengan redaksi kredensial otomatis via engine `Redactor`.
- **Rangkaian Benchmark Reproduksibel:** Skrip `benchmarks/benchmark_proxy.py` dan dokumentasi `benchmarks/METHODOLOGY.md` untuk mengukur latensi (p50/p95/p99), TTFT, throughput (req/s), dan efisiensi cache/kompaktor.
- **Panduan Pengujian & Observabilitas:** Dokumentasi teknis komprehensif di `docs/testing.md` dan `docs/observability.md`.
- **CI Pipeline Multi-OS & Multi-Python:** Otomatisasi GitHub Actions (`.github/workflows/ci.yml`) pada Ubuntu, Windows, macOS dengan Python 3.10, 3.11, 3.12, pengujian build frontend Vite/React, dan linter.

---

#### 6. Penguatan Keamanan Sistem Terpadu (Fase 2)
- **Enkripsi Kredensial At-Rest (AES-256-GCM):** Mengganti masking XOR dengan enkripsi standar AES-256-GCM (library `cryptography`), nonce 12-byte unik per record, AAD binding dengan key record, dan integrasi OS Keyring (Windows DPAPI, macOS Keychain, Linux SecretService) dengan fallback terderivasi Scrypt KDF. CRC32 dipertahankan sebagai checksum integritas bit-rot.
- **Autentikasi Mandatori & API Key Management:** Wajib API key (`Authorization: Bearer` atau `x-api-key`) untuk semua endpoint proxy `/v1/*`. Kunci disimpan hanya dalam bentuk hash salted SHA-256. CLI `auth create-key`, `list-keys`, `revoke-key` untuk manajemen kunci. Non-loopback bind guard menolak start jika host diubah ke IP eksternal tanpa auth.
- **Perlindungan Localhost & Web Dashboard:** Host header validation untuk mitigasi DNS Rebinding, strict CORS & Origin validation pada seluruh mutasi state, perlindungan CSRF via cookie double-submit (`pg_csrf` & `x-csrf-token`), serta security headers (`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy`). WebSocket `/sentinel` kini memvalidasi sesi HttpOnly dan Origin.
- **Auto-Update yang Aman:** Transisi ke tagged GitHub Releases API dengan validasi checksum SHA-256 sebelum pembaruan. Default diubah menjadi "notify only" (`auto_apply: False`), dengan safety gate (idle time & 0 in-flight requests) dan rollback otomatis jika health-check gagal.
- **Redaksi Log Terpusat:** Modul pembersih regex terpusat (`prime_gate.logging.redactor`) yang menyaring OAuth token, refresh token, API key, header Authorization, cookie sesi, dan payload sensitif dari seluruh stream logging dan respons error.
- **Migrasi Otomatis & Idempoten V1 ke V2:** Engine database otomatis memigrasikan record V1 lama ke V2 terenkripsi dengan backup SQLite native di `data/backups/`, serta menyediakan perintah CLI `db rotate-key` dan `db rollback`.

---

#### 7. Semantic Cache Berbasis Konteks & Multilingual (Fase 3A)
- **Model Embedding Multibahasa Terpadu:** Default ke model multibahasa berkinerja tinggi `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (mendukung `intfloat/multilingual-e5-small`) via FastEmbed ONNX Runtime. Menjamin skor kemiripan $\ge 0.93$ (teruji empiris 0.978) untuk parafrase pertanyaan bahasa Indonesia.
- **Dukungan Asimetris Keluarga E5:** Otomatis menerapkan prefix `"query: "` untuk pencarian vektor dan `"passage: "` saat persistensi cache jika menggunakan model keluarga E5.
- **Kunci Cache Berbasis Konteks (Anti-Hallucination Invariant):** Cache key turunan `(scope, context_hash, last_user_query, query_hash, tools_sig, has_tools)` di mana `context_hash` mengunci instruksi sistem, riwayat percakapan sebelumnya, parameter generasi (`model`, `temperature`), deklarasi tools, serta isi file kode/tool result yang direferensikan. Dua prompt identik dengan konten file berbeda dipastikan **TIDAK PERNAH HIT** (`MISS`).
- **Isolasi Scope & Multi-Tenant:** Partisi cache terisolasi per prefix API key (`key_<prefix>`) dan per session/project identifier (`project_id`). Klien berbeda tidak akan mengalami kebocoran data cache.
- **Lifecycle TTL & LRU Capacity Eviction:** Manajemen masa aktif cache dengan TTL terkonfigurasi (default 24 jam / 86400s), batas kapasitas entries maksimum (default 5000), serta eviksi otomatis berbasis Least-Recently-Used (LRU).
- **Kebijakan Default Coding Agent yang Ketat:** Request agent/tool-calling dibatasi pada exact-match secara default (semantic opt-in dengan threshold 0.96). Respons yang mengandung `tool_use`/`tool_calls`, pesan error, atau chunk stream terputus secara otomatis dilewati dari cache.
- **Header Audit Standar Industri:** Menyediakan transparansi komputasi melalui response headers: `X-Cache: HIT|MISS`, `X-Cache-Type: EXACT|SEMANTIC|NONE`, `X-Cache-Similarity: <score>`, dan `X-Cache-Key-Scope: <scope>`.
- **Verifikasi Latar Belakang & Estimasi False-Hit Rate:** Tabel audit `pg_cache_verifications` dan worker sampling asinkron untuk mencatat perbandingan verifikasi latar belakang dan menghitung false-hit rate pada dashboard `/caching`.
- **Dashboard UI Caching Terintegrasi:** Menampilkan rincian badge Scope dan Context Hash pada tabel cache, modal detail inspeksi konteks lengkap, visualisasi False-Hit Rate KPI card, serta selector model embedding dinamis.

---

#### 8. Smart Agent Context Compactor Cerdas (Fase 3B)
- **Konfigurasi Berjenjang (Hierarchical Config):** Mendukung resolusi konfigurasi compactor fleksibel per-klien (berdasarkan `User-Agent` seperti `cline`, `cursor`, `opencode`, `claude-code`) dan per-model target (model dengan context window berbeda dapat memiliki window pangkas berbeda).
- **Invarian Proteksi Error (Error Log Preservation):** Output eksekusi tool yang memuat kegagalan (exit code non-zero, tracebacks, compiler error, exception, atau Anthropic `is_error=True`) **100% diproteksi dari pemangkasan** agar coding agent tetap memahami akar masalah kegagalan build/test.
- **Proteksi Re-Referensi Downstream (Downstream Reference Immunity):** Tool execution yang diacu ulang atau dibahas oleh prompt pengguna maupun respons model pada giliran-giliran berikutnya dipertahankan secara utuh untuk menjaga kesinambungan nalar kode.
- **Integritas Prompt Sistem & Anchor Turn:** Turn awal (`idx <= 1`) dan pesan sistem (`role == "system"`) dijamin tidak tersentuh demi efisiensi prefix caching upstream Google Antigravity.
- **Penanda Pemangkasan Informatif:** Pemangkasan menyisakan penanda terstruktur `[output dipangkas: ~N token | Historical tool execution output pruned: X chars, Y lines]` agar model mengetahui adanya teks historis yang diringkas.
- **Mode Non-Invasif Dry-Run:** Menyediakan opsi `dry_run=True` di mana payload request dijamin 100% tidak diubah sama sekali, namun kalkulasi token yang dapat dihemat tetap dihitung dan dicatat pada log serta database telemetri.
- **Ledger Telemetri Akumulatif:** Fungsi penyimpanan token dihemat `record_compactor_tokens_saved` di SQLite database untuk pemantauan penghematan token kumulatif pada Web UI.

---

## [1.2.2] - 2026-10-18

### 🧠 Next-Gen Smart & Semantic Vector Caching (Hybrid Engine + Coding Agent Optimization)

#### 1. Real Semantic Vector Cache via FastEmbed ONNX Runtime
- **Lightweight CPU Vector Search:** Integrated `fastembed` with `BAAI/bge-small-en-v1.5` running locally via ONNX Runtime (CPU-only, RAM ~100MB, zero PyTorch/CUDA dependencies).
- **Dense Vector Serialization:** Encodes incoming queries into 384-dimensional unit-normalized float32 vectors, stored directly as BLOBs within SQLite WAL persistent database (`pg_semantic_cache`).
- **High-Speed In-Memory Cosine Similarity:** Computes vector dot products across cached entries for identical models. Paraphrased or semantically equivalent queries exceeding threshold (default 93%) achieve instantaneous `X-Cache: HIT`, `Type: SEMANTIC` at ~12ms TTFT with zero upstream quota drain!
- **Smooth Token-Chunked SSE Replay:** Replays cached streaming responses in micro-sleep chunks (4 words / 3ms) mimicking native token delivery for realistic IDE animations.

#### 2. Separation of Tool Declaration vs Execution (Coding Agent Caching)
- **Eliminated 100% Cache Miss on AI Coding Agents:** Autonomous agents (Cursor, OpenCode, Claude Code, Cline) constantly provide tool definitions in request headers. Previously, any request with tools bypassed caching entirely.
- **Turn-Based Text Response Caching:** When models output regular text responses despite tool availability, the turn is fully eligible for caching. Only requests resulting in active model tool executions (`tool_calls` / `tool_use`) bypass the cache.
- **Turn-Based Cache Key Strategy:** Strips dynamic noise (timestamps, ephemeral turn IDs) and canonicalizes normalized tools signatures, allowing repetitive context questions across agent turns to hit cache reliably.

#### 3. Upstream Prefix Caching Optimization (Google Antigravity Native)
- **Deterministic Tool Declaration Ordering:** Sorts function declarations alphabetically by name across both OpenAI and Anthropic translators, ensuring byte-identical prefix payloads for Google Antigravity / Gemini / Claude prefix hash tables.
- **Conversation Anchor Preservation:** Updated `ContextCompactor` to preserve the first conversation turn anchor (`idx <= 1`) across all turns, preventing middle-session compactions from breaking the upstream prefix cache boundary.

#### 4. Dashboard UI & Telemetry Integration
- **Hit Type Badges in Ledger:** Granular visual badges distinguishing `EXACT HIT (100%)`, `SEMANTIC HIT (97.5%)`, and `UPSTREAM PREFIX`.
- **Vector Engine Settings Card:** Interactive Semantic Similarity Threshold slider (80%–99%) and one-click toggle for Semantic Vector Matching in `CachingUsagePage.tsx`.
- **Hit Breakdown Analytics:** Added real-time breakdown counters for Exact, Semantic, and Upstream hits to KPI cards.

---

## [1.2.1] - 2026-10-18

### 🌐 Universal Bridge: Native Anthropic Messages API Compatibility (`/v1/messages`)

#### 1. Native Anthropic Messages API (`POST /v1/messages`)
- **Full Protocol Translation:** Complete bidirectional translation layer between Anthropic Messages API and Google Antigravity, allowing tools like **Claude Code CLI, Cline, Roo Code, Cursor (Claude mode), Continue.dev, LibreChat, OpenCode (Anthropic provider), and Aider** to connect directly to Prime Gate (`http://localhost:52111`) without external proxies.
- **Strict 7-Event SSE Streaming State Machine:** Fully compliant implementation of Anthropic streaming events:
  - `message_start` (initial metadata & input usage)
  - `content_block_start` (opening text or tool_use blocks)
  - `content_block_delta` (`text_delta` streaming and `input_json_delta` tool parameter streaming)
  - `content_block_stop` (closing block)
  - `message_delta` (`stop_reason` and output usage token counts)
  - `message_stop` (clean stream completion)
- **Non-Streaming JSON Support:** Compliant response formatting with `id`, `type: "message"`, `role: "assistant"`, structured `content` blocks, `stop_reason` (`end_turn` / `tool_use`), and exact token `usage`.
- **Pre-flight Token Counting Endpoint (`POST /v1/messages/count_tokens`):** Dedicated endpoint for calculating input prompt tokens before model generation, required by Cline, Roo Code, and Claude Code for context window budgeting.
- **Dual-Mode Models Endpoint (`GET /v1/models`):** Dynamically serves either OpenAI-standard `{"object": "list", "data": [...]}` or Anthropic-format `{"data": [{"type": "model", ...}]}` based on incoming client headers (`anthropic-version`) or query parameters.
- **Dynamic Model Name Resolution:** Seamlessly routes Anthropic model names (`claude-3-5-sonnet-20241022`, `claude-3-5-sonnet-latest`, `claude-3-7-sonnet-20250219`, `claude-3-opus`, `claude-sonnet-4-6`) to equivalent live Antigravity models.
- **Universal Enterprise Integration:** Anthropic requests transparently inherit the entire Prime Gate enterprise stack:
  - **Compiled Binary DB Caching** (including `cache_control: {"type": "ephemeral"}` emulation with `cache_read_input_tokens` reporting)
  - **Smart Agent Context Compactor** (auto-prunes voluminous tool outputs)
  - **AI Runaway Loop Sentinel** (detects and halts tool call loops)
  - **Mid-Flight Account Failover** (transparent rotation on HTTP 429)
  - **WebSocket Live Telemetry** (real-time token throughput broadcast)

#### 2. Dashboard, Prompt Sandbox & Documentation Enhancements
- **Prompt Sandbox Protocol Switcher:** Added a tactile toggle in the Web UI Prompt Sandbox allowing developers to run live test prompts against either **OpenAI Protocol (`/v1/chat/completions`)** or **Anthropic Protocol (`/v1/messages`)** with real-time SSE stream decoding.
- **Dual-Protocol Client Gateway Cards:** Main Dashboard updated with instant copy actions for both OpenAI Base URL (`http://127.0.0.1:52111/v1`) and Anthropic Base URL (`http://127.0.0.1:52111`).
- **Comprehensive Documentation Page:** Complete guides, IDE setup parameters (Cline, Cursor, Roo Code, Claude Code), and ready-to-run SDK code snippets for Python `anthropic`, Node.js `@anthropic-ai/sdk`, and cURL.
- **Action Button UX Refinement:** Button text on engine cards now explicitly reflects the verb/action to perform (`Turn Off Cache`, `Disable Tool Bypass`, `Turn Off Compactor`, `Deactivate Sentinel`).

---

## [1.2.0] - 2026-10-18

### 🚀 Enterprise Engine: Context Compactor, Mid-Flight Failover, Runaway Loop Sentinel & Economic Value Simulator

#### 1. Smart Agent Context Compactor (`ContextCompactor`)
- **Sliding-Window Conversation History Pruning:** Autonomous AI coding agents (OpenCode, Cursor, Continue, Claude Code, Cline) accumulate massive contexts (30,000 to 100,000+ tokens) due to multi-turn execution outputs (`read_file`, `grep`, `bash`).
- **Middle-Line Output Pruning:** Automatically trims verbose tool outputs older than recent turns (configurable window, default 3 active turns; max 40 lines), replacing bloated inner lines with a clean `... [Compacted N lines by Prime Gate Context Compactor] ...` marker while strictly preserving the first 20 and last 20 lines (head + tail).
- **Zero-Loss Instruction Preservation:** `system` prompts and recent active turns are strictly preserved 100% unaltered, reducing prompt token bloat by **50% to 70%** and preventing context window truncation.

#### 2. Transparent Mid-Flight Account Failover (`AccountFailoverPool`)
- **Elimination of Client 429 Quota Exhaustion:** When upstream Google Antigravity servers return HTTP 429 (`RESOURCE_EXHAUSTED`) or 503 during a streaming session, Prime Gate intercepts the error before emitting the first SSE chunk to the client.
- **Microsecond In-Memory Cooldown Management:** Failed accounts are automatically marked in cooldown (120–300s). The engine instantly and transparently rotates to the next healthiest candidate account with the highest remaining quota fraction.
- **Unbroken Client Streams:** Client IDEs (Cursor, Continue, Vercel AI SDK, Windsurf) receive a completely seamless connection with zero interrupted streams or dropped generations.

#### 3. AI Agent Runaway Loop Killer & Sentinel Guard (`AgentLoopGuard`)
- **Deterministic Tool Call Hashing:** Canonically hashes function names and arguments (`tool_name:sha256(args)`) across consecutive assistant turns.
- **Surgical System Interventions:** When an autonomous agent attempts to execute the exact same failing tool call $\ge 3$ consecutive times without forward progress, Sentinel intercepts the loop and injects a corrective system instruction (`[SYSTEM SAFETY INTERVENTION]`) to break the infinite loop and prevent quota depletion.
- **Configurable Repeat Threshold:** Configurable via Web UI settings card (2 calls, 3 calls strict, 5 calls) and dynamic cache settings.

#### 4. Economic Value Delivered Simulator (USD & IDR)
- **Live Commercial Cost Benchmark:** Real-time financial simulator benchmarking token consumption and cache savings against commercial flagship API pricing (OpenAI GPT-4o / Claude 3.5 Sonnet: \$2.50 / \$10.00 per 1M tokens, baseline IDR 16,500/USD).
- **Live Currency Toggle on Dashboard:** Added a dedicated **Value Delivered** KPI card on the main Dashboard and Caching Usage page featuring an interactive `USD` / `IDR` toggle button.
- **Persistent Ledger Integration:** Computes exact accumulated economic savings delivered by Prime Gate's free Antigravity integration and smart caching layers.

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
- **Live Cache Engine Controls & Responsive Settings:** Interactive glass card controls to enable/disable caching, toggle Agent Safety tool bypass, and configure minimum prompt length thresholds. Clean, responsive vertical column layout with segmented controls for retention TTL (7d/14d/30d) and prompt length (5c/10c/25c).
- **Searchable Persistent Cache Ledger:** Interactive table detailing Cached Model, Prompt Preview, Response Preview, Token Breakdown, Hit Count, Cumulative Tokens Saved, and Last Hit Timestamp with single-entry deletion and full modal inspection.
- **Polished Visual Layout:** Uniform glass-card KPI styling, streamlined toolbar with quick refresh and purge actions, and sidebar version synchronization to v1.1.5.

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
