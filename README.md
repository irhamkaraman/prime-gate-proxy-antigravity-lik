# ⚡ Prime Gate Proxy Antigravity (`prime-gate-proxy-antigravity-lik`)

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-green.svg)](https://nodejs.org)
[![License](https://img.shields.io/badge/license-MIT-purple.svg)](LICENSE)
[![Protocol](https://img.shields.io/badge/API-OpenAI%20Compatible-orange.svg)](https://platform.openai.com/docs/api-reference)

> **Production-grade, OpenAI-compatible proxy gateway for Google Antigravity.**
> Menghubungkan Google Antigravity (Cloud Code Companion API) ke seluruh AI client modern (**OpenCode**, **Cursor**, **Continue.dev**, **SillyTavern**, dsb.) dengan **Live Quota Radar**, **SSE Streaming**, **Thinking (Reasoning) Chunks**, **Interactive Rich CLI**, dan **Glassmorphic Web UI Dashboard**.

---

## 🚀 Keunggulan Utama (Key Features)

- 🔄 **100% OpenAI API Compatible:** Mengekspos endpoint standar `/v1/models` dan `/v1/chat/completions` (baik streaming `text/event-stream` maupun non-streaming).
- 🧠 **Extended Thinking (Reasoning Mode):** Mengalirkan chunk penalaran model secara real-time (`delta.reasoning_content`) untuk model `Claude Sonnet 4.6 (Thinking)` dan `Claude Opus 4.6 (Thinking)`.
- 📊 **Dynamic Quota & Tier Detection:** Mendeteksi secara otomatis tier langganan akun Google bosss (**`Google AI Pro (Trial / Reliance Jio 18M Promo)`** vs **`Google AI Pro (Paid)`**) dan memfilter katalog model yang valid.
- 🛡️ **Zero 400 Bad Request (Recursive Schema Sanitizer):** Membersihkan atribut JSON Schema yang tidak didukung Antigravity (seperti `exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`) sehingga pemanggilan tool/function calling selalu stabil tanpa crash.
- 💻 **Rich CLI Terminal & Help Desk:** Dilengkapi styling visual terminal modern via `rich` & `typer` (`--version`, `auth login`, `auth import`, `quota`, `daemon start|stop|status`).
- 🌐 **Modern Glassmorphic Web UI:** Dashboard visual berbasis Node.js untuk melihat status server, indikator persentase kuota, uptime, katalog model, serta *live interactive prompt playground*.
- 🪟 **Detached Windows Background Daemon:** Dapat dijalankan di background secara headless tanpa jendela terminal yang mengganggu.

---

## 📐 Arsitektur Sistem

```
┌────────────────────────────────────────────────────────┐
│             AI Clients (OpenCode, Cursor, etc)         │
└──────────────────────────┬─────────────────────────────┘
                           │ OpenAI REST / SSE Stream
                           ▼
┌────────────────────────────────────────────────────────┐
│           Python Core Engine (FastAPI :52111)           │
│  ├── /v1/models                                        │
│  ├── /v1/chat/completions                              │
│  ├── Quota Monitor & Dynamic Tier Engine               │
│  └── JSON Schema Sanitizer (Clean exclusiveMinimum)    │
└──────────────┬───────────────────────────▲─────────────┘
               │ Internal State Sync       │ Status / Proxy
               ▼                           │
┌──────────────────────────────┐ ┌────────┴──────────────┐
│ accounts.json (Google OAuth) │ │ Node.js Web UI (:52110)│
│  - Refresh Token             │ │  - Quota Radar Meter  │
│  - Cached Quota Fractions    │ │  - Prompt Playground  │
└──────────────┬───────────────┘ └───────────────────────┘
               │ HTTPS / OAuth2 Token Refresh
               ▼
┌────────────────────────────────────────────────────────┐
│       Google Antigravity Upstream (Cloud Companion)     │
│   (Claude 4.6 Thinking, Gemini 3.8 Flash, GPT-OSS)     │
└────────────────────────────────────────────────────────┘
```

---

## 🛠️ Persyaratan Sistem

- **OS:** Windows 10/11, Linux, atau macOS
- **Python:** Versi 3.10 atau lebih baru (FastAPI, Uvicorn, HTTPX, Pydantic, Typer, Rich)
- **Node.js:** Versi 18.x atau lebih baru (Zero external npm dependency untuk Web UI)

---

## 📦 Instalasi Cepat

1. **Clone repository ini:**
   ```bash
   git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
   cd prime-gate-proxy-antigravity-lik
   ```

2. **Install dependencies Python:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Atau jalankan file `scripts\install.bat` di Windows)*

3. **Impor atau Hubungkan Akun Google Antigravity:**
   - **Jika bosss sudah menggunakan OpenCode:**
     ```bash
     python -m prime_gate.cli auth import
     ```
   - **Atau login akun Google baru via browser:**
     ```bash
     python -m prime_gate.cli auth login
     ```

---

## 🕹️ Panduan Penggunaan CLI

Gunakan perintah bawaan `python -m prime_gate.cli` (atau jalankan script `bin\prime-gate.cmd` di Windows):

### 1. Cek Versi & Bantuan
```bash
python -m prime_gate.cli --version
python -m prime_gate.cli --help
```

### 2. Cek Real-time Kuota & Model Catalog
```bash
python -m prime_gate.cli quota
```
*Output menampilkan tabel visual status kuota sisa, waktu reset, dan tier akun Google AI Pro.*

### 3. Manajemen Akun
```bash
# Lihat daftar akun tersimpan
python -m prime_gate.cli auth list

# Impor akun dari OpenCode global config
python -m prime_gate.cli auth import

# Tambah akun baru via Google OAuth Login di browser
python -m prime_gate.cli auth login
```

### 4. Menjalankan Server
- **Mode Background (Daemon Tersembunyi):**
  ```bash
  python -m prime_gate.cli daemon start
  python -m prime_gate.cli daemon status
  python -m prime_gate.cli daemon stop
  ```
- **Mode Foreground (Live Terminal Logs):**
  ```bash
  python -m prime_gate.cli start --port 52111
  ```
- **Membuka Web UI Dashboard:**
  ```bash
  python -m prime_gate.cli ui --port 52110
  ```
  *(Atau buka langsung browser ke `http://127.0.0.1:52110`)*

---

## 🖥️ Web UI Dashboard Preview

Akses dashboard visual di **`http://127.0.0.1:52110`**:
- 📡 **Live Quota Gauges:** Bar persentase kuota Claude Family dan Gemini Flash secara real-time.
- 🎯 **Tier Badge:** Otomatis menampilkan `Google AI Pro (Trial / Reliance Jio 18M Promo)` atau `Paid`.
- 🧪 **Interactive Prompt Sandbox:** Uji langsung instruksi dan lihat kecepatan inferensi (*Time To First Token* / TTFT) serta *thinking process* model.
- 📋 **One-Click Config Copy:** Salin endpoint konfigurasi untuk client AI bosss dengan satu klik.

---

## ⚙️ Integrasi dengan OpenCode

Untuk menghubungkan **OpenCode** ke Prime Gate Proxy, sesuaikan konfigurasi di `~/.config/opencode/opencode.json`:

```json
{
  "providers": {
    "antigravity": {
      "baseUrl": "http://127.0.0.1:52111/v1",
      "apiKey": "local-prime-gate-proxy",
      "models": [
        "claude-sonnet-4-6",
        "claude-opus-4-6-thinking",
        "gemini-3.8-flash",
        "gemini-2.5-pro"
      ]
    }
  }
}
```

---

## 📂 Struktur Direktori Project

```text
prime-gate-proxy-antigravity-lik/
├── package.json               # Node.js metadata & script commands
├── pyproject.toml             # Python PEP 517/621 package metadata
├── requirements.txt           # Python core dependencies
├── README.md                  # Dokumentasi resmi
├── LICENSE                    # MIT License
├── .gitignore                 # Cache & sensitive file exclusion
├── bin/
│   ├── prime-gate.cmd         # Windows CLI command wrapper
│   └── prime-gate.js          # Node.js CLI runner
├── prime_gate/                # Python Core Engine
│   ├── __init__.py            # Versi & metadata
│   ├── cli.py                 # Rich CLI Suite
│   ├── config.py              # Port, endpoint, dan model mappings
│   ├── server.py              # FastAPI OpenAI endpoints & SSE streaming
│   ├── auth/                  # OAuth & Account Manager
│   ├── quota/                 # Quota Monitor & Subscription Tier Detector
│   ├── translator/            # OpenAI <-> Antigravity Converter & Schema Sanitizer
│   └── daemon/                # Background Process Manager (Windows)
├── ui/                        # Node.js Web UI
│   ├── server.js              # Native HTTP proxy server untuk UI
│   └── public/                # Static assets (HTML, CSS Glassmorphism, JS)
└── scripts/
    ├── install.bat            # Installer otomatis
    ├── start-all.bat          # Startup script sekali klik
    └── stop-all.bat           # Shutdown script
```

---

## 📄 Lisensi & Kontributor

- **Author:** [Irham Karaman](https://github.com/irhamkaraman)
- **License:** MIT License

*Dibuat untuk memudahkan developer memanfaatkan kapabilitas Google Antigravity secara bebas, fleksibel, dan performan.*
