<div align="center">

<img src="../../docs/images/prime_gate_dual_protocol.svg" alt="Prime Gate Dual Protocol - Gateway OpenAI & Anthropic Kompatibel untuk Google Antigravity" width="100%" />

<br/><br/>

# ⚡ Prime Gate Antigravity Proxy
### `prime-gate-antigravity`

**Gateway Proksi Mandiri (Self-Hosted) Tingkat Perusahaan Kompatibel OpenAI & Anthropic untuk Google Antigravity.**

[![NPM Version](https://img.shields.io/npm/v/prime-gate-antigravity.svg?style=for-the-badge&logo=npm&color=CB3837)](https://www.npmjs.com/package/prime-gate-antigravity)
[![Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependencies)
[![Dependents](https://img.shields.io/badge/dependents-0-blue.svg?style=for-the-badge&logo=npm)](https://www.npmjs.com/package/prime-gate-antigravity?activeTab=dependents)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)
[![CI](https://img.shields.io/badge/CI-Passing-brightgreen.svg?style=for-the-badge&logo=githubactions&logoColor=white)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik/actions)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-purple.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)

---

### 🌐 Pilih Bahasa & Dokumentasi
[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

📸 [**Lihat Galeri Tangkapan Layar Dasbor Lengkap**](../../docs/SCREENSHOTS.md) • 📚 [**Panduan Pengguna & Integrasi Komprehensif**](../../docs/USER_GUIDE.md)

---

</div>

## 🚀 Pemasangan & Menjalankan Cepat (Windows, macOS, Linux)

Jalankan Prime Gate secara instan di sistem Anda tanpa perlu clone repo manual:

```bash
# Opsi 1: Jalankan langsung tanpa instalasi (via NPX)
npx prime-gate-antigravity

# Opsi 2: Pasang secara global di sistem Anda (Direkomendasikan)
npm install -g prime-gate-antigravity@latest

# Jalankan daemon di latar belakang (Proxy API :52111 + Web UI :52110)
# Mendukung penuh Windows, macOS, dan Linux
prime-gate daemon start
```

### 🎛️ Bendera & Opsi Perintah (Flags)
| Bendera / Opsi | Keterangan | Nilai Standar |
| :--- | :--- | :--- |
| `--host <alamat>` | Alamat IP host server proksi | `127.0.0.1` |
| `--port <angka>` | Port API proksi (endpoint OpenAI & Anthropic) | `52111` |
| `--ui-port <angka>` | Port Dasbor Web UI Glassmorphic | `52110` |
| `--daemon` | Jalankan atau kelola proses di latar belakang | `false` |
| `--version`, `-v` | Tampilkan versi yang terpasang saat ini | `1.2.8` |
| `--help`, `-h` | Tampilkan bantuan & seluruh daftar perintah | - |

---

## ⚠️ Disclaimer & Risiko (Ketentuan & Batasan Tanggung Jawab)

> [!WARNING]
> **Perangkat Lunak Open-Source Independen & Peringatan Risiko:**
> - **Prime Gate Antigravity Proxy** adalah proyek open-source independen dan **tidak berafiliasi, didukung, atau disetujui** oleh Google LLC maupun Anthropic PBC.
> - Mengakses endpoint internal Google Antigravity di luar ekstensi resmi dapat berpotensi melanggar ketentuan layanan.
> - **PERINGATAN KEAMANAN AKUN:** **JANGAN PERNAH** menggunakan akun Google utama, email pekerjaan, atau akun pribadi sensitif Anda. Selalu gunakan akun Google sekunder khusus eksperimen. Seluruh risiko penggunaan ditanggung sepenuhnya oleh pengguna.

---

## 🤖 Katalog Model Terbaru yang Didukung

Prime Gate secara dinamis mengonversi model upstream Google Antigravity menjadi slug standar kompatibel OpenAI dan Anthropic:

| Nama Model | Slug API | Context Window | Penalaran (Thinking) | Modalitas | Paling Cocok Untuk |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Claude Sonnet 4.6** | `claude-sonnet-4-6` | 200,000 token | ✅ Adaptive CoT | Teks + Visi | Agentic coding, Claude Code CLI, Cline, Roo Code |
| **Claude Opus 4.6** | `claude-opus-4-6` | 200,000 token | ✅ Deep Reasoning | Teks + Visi | Perancangan arsitektur kompleks & refactoring |
| **Gemini 3.8 Flash** | `gemini-3.8-flash` | 1,000,000 token | ✅ Sangat Cepat | Multimodal | Throughput tinggi, payload besar, review cepat |
| **Claude 3.7 Sonnet** | `claude-3-7-sonnet` | 200,000 token | ✅ Hybrid Thinking | Teks + Visi | Diskusi interaktif multi-turn & pair programming |
| **Claude 3.5 Sonnet** | `claude-3-5-sonnet` | 200,000 token | ❌ Standar | Teks + Visi | Coding umum & pemanggilan tools standar |

---

## ⌨️ Kumpulan Seluruh Perintah Terminal (Cheatsheet)

Semua perintah dapat dipanggil via `prime-gate <perintah>` (jika terpasang global) atau `npx prime-gate-antigravity <perintah>`:

### 1. Manajemen Service & Daemon
```bash
prime-gate daemon start       # Nyalakan layanan latar belakang (Proxy API + Web UI)
prime-gate daemon status      # Cek status PID, memori, dan uptime daemon
prime-gate daemon stop        # Matikan seluruh layanan latar belakang
prime-gate daemon restart     # Mulai ulang layanan latar belakang secara bersih
prime-gate start              # Jalankan proksi langsung di jendela terminal aktif
prime-gate ui                 # Buka dasbor Web UI secara langsung
```

### 2. Autentikasi Akun Google
```bash
prime-gate auth login         # Login OAuth interaktif Google (buka peramban otomatis)
prime-gate auth list          # Tampilkan daftar akun Google yang tersambung
prime-gate auth switch <mail> # Ganti akun utama Google yang sedang aktif
prime-gate delete-account --email <mail> # Hapus satu akun tertentu
prime-gate clear-accounts     # Hapus semua akun tersambung sekaligus
```

### 3. API Key Klien Gateway & Kebijakan Akses
```bash
# Buat API key klien baru dengan batas RPM dan kuota token per hari
prime-gate keys create --name "DevCursor" --rpm 60 --tpd 1000000
prime-gate keys list          # Tampilkan daftar API key aktif beserta limitnya
prime-gate keys revoke <id>   # Cabut akses untuk API key tertentu seketika
```

### 4. Kuota, Pembaruan & Pemeliharaan Database
```bash
prime-gate quota              # Lihat sisa kuota langsung untuk seluruh model
prime-gate check-update       # Cek ketersediaan versi terbaru di npmjs.org
prime-gate db check           # Jalankan uji integritas CRC32 & diagnosis database
prime-gate db vacuum          # Kompres dan rapikan fragmentasi file SQLite WAL
prime-gate db rollback        # Pulihkan database dari snapshot cadangan sebelumnya
```

---

## 🔌 Panduan Singkat Integrasi Klien AI

Hubungkan asisten AI favorit Anda ke Prime Gate dalam hitungan detik:

### 1. Claude Code CLI (Protokol Asli Anthropic)
```bash
# Pasang environment variables
export ANTHROPIC_BASE_URL="http://127.0.0.1:52111"
export ANTHROPIC_API_KEY="pg-live-..."  # Dibuat via: prime-gate keys create

# Jalankan Claude Code secara langsung
claude --model claude-sonnet-4-6
```

### 2. Cursor IDE / OpenCode / Cline / Continue.dev (OpenAI & Anthropic API)
* **Base URL:** `http://127.0.0.1:52111/v1`
* **API Key:** `pg-live-...` (Dibuat via perintah `prime-gate keys create` atau Dasbor Web UI)
* **Model ID:** `claude-sonnet-4-6` atau `gemini-3.8-flash`

📖 *Panduan lengkap untuk Aider, Roo Code, LibreChat, dan integrasi SDK tersedia di [Panduan Pengguna Lengkap](../../docs/USER_GUIDE.md#6-ai-client--ide-integration-guide).*

---

## 📸 Galeri Tampilan Antarmuka Dasbor Web

Prime Gate dilengkapi Dasbor Web UI bertema dark glassmorphism modern di `http://127.0.0.1:52110`:

* **Telemetri Live & Kecepatan Token** (`/dashboard`)
* **Buku Besar Request & Benchmark Latensi** (`/benchmarks`)
* **Manajemen Multi-Akun & Status Kuota** (`/accounts`)
* **Playground & Prompt Sandbox Streaming** (`/sandbox`)
* **Sentinel Pengawas Integritas SQLite WAL** (`/sentinel`)

👉 **[Buka Galeri Tangkapan Layar Dasbor Resolusi Penuh](../../docs/SCREENSHOTS.md)**

---

## ❓ Troubleshooting & Tanya Jawab

### 1. `503 Service Unavailable: MODEL_CAPACITY_EXHAUSTED`
* **Penyebab:** Server Google Antigravity sedang mengalami beban puncak untuk model tersebut.
* **Solusi:** Prime Gate akan otomatis memindahkan request ke akun cadangan Anda. Anda juga bisa mengganti akun via `prime-gate auth switch <email-lain>` atau beralih ke `gemini-3.8-flash`.

### 2. `Errno 10048 / Address already in use`
* **Penyebab:** Port `52111` atau `52110` sedang digunakan oleh proses lain atau daemon lama.
* **Solusi:** Hentikan proses via `prime-gate daemon stop`, atau tentukan nomor port lain:
  ```bash
  prime-gate start --port 52120 --ui-port 52121
  ```

### 3. `401 Unauthorized` Saat AI Klien Mengirim Request
* **Penyebab:** Header Client Gateway API Key belum terpasang atau salah.
* **Solusi:** Buat kunci baru via `prime-gate keys create --name "DevKey"`, lalu masukkan nilai kuncinya pada header `Authorization: Bearer pg-live-...` atau `x-api-key`.

### 4. `Perintah prime-gate tidak dikenali` (Pengguna Windows)
* **Solusi:** Pasang secara global lewat `npm install -g prime-gate-antigravity@latest`, atau jalankan skrip `scripts\setup-path.ps1` untuk menambahkan direktori Python ke PATH sistem secara otomatis.

---

## 📜 Riwayat Versi & Changelog

| Versi | Tanggal Rilis | Inovasi Utama & Pembaruan |
| :--- | :--- | :--- |
| **v1.2.6** | 2026-10-23 | **Dokumentasi Modular & Pemolesan NPM:** Hero install npm tanpa dependensi eksternal, pemisahan galeri UI (`docs/SCREENSHOTS.md`), proteksi encoding ASCII cp1252 Windows, dan cheatsheet terpadu. |
| **v1.2.5** | 2026-10-23 | **Distribusi Global NPM:** Paket npm global `prime-gate-antigravity`, pemeriksa pembaruan dwiarah, automator PATH Windows 1-klik, dan pipeline GitHub Actions CD. |
| **v1.2.4** | 2026-10-23 | **Penegakan Kebijakan API Key Klien:** Pembatasan RPM/TPD granular, budget kuota token, whitelist model dinamis, dan isolasi partisi cache (`cache_scope="key"`). |
| **v1.2.3** | 2026-10-22 | **Auto-Update Otonom Tanpa Sentuhan:** Pembaruan background pada kondisi idle, MCP pencarian web DoH anti-blokir ISP (`scripts/mcp_search.py`), dan cache tanda tangan pemikiran Gemini 3. |
| **v1.2.2** | 2026-10-22 | **Caching Vektor Semantik Generasi Baru:** Mesin hybrid vektor FastEmbed (~12ms latensi), verifikasi integritas SQLite WAL CRC32 32-bit, dan enkripsi data AES-256-GCM. |
| **v1.2.1** | 2026-10-21 | **Universal Bridge (Protokol Asli Anthropic):** Endpoint `/v1/messages` langsung dengan mesin status streaming SSE 7-event untuk Claude Code & Cline. |
| **v1.1.5** | 2026-10-20 | **Dasbor Web UI Glassmorphic:** Dasbor React 18, pemantauan WebSocket Sentinel, buku besar audit request, dan telemetri real-time. |

📖 *Rincian log perubahan lengkap tersedia di [CHANGELOG.md](../../CHANGELOG.md) dan [GitHub Releases](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik/releases).*

---

## 🔍 Batasan yang Diketahui (Known Limitations)

1. **Ketergantungan Kuota Upstream:** Batas kuota inferensi, ketersediaan model, dan laju request sepenuhnya diatur oleh kebijakan server Google Cloud.
2. **Perubahan Skema API Internal:** Beroperasi langsung dengan API internal Antigravity, sehingga modifikasi skema dari Google mungkin memerlukan penyesuaian adaptor.
3. **Alat Pengembang Personal:** Dirancang khusus untuk kenyamanan alur kerja pengembang mandiri dan eksperimen agen lokal, bukan untuk platform komersial berskala besar.

---

## 🛡️ Model Ancaman (Threat Model)

| Batasan / Aset | Mekanisme Proteksi (Dalam Cakupan) | Di Luar Cakupan (Tidak Terproteksi) |
| :--- | :--- | :--- |
| **Kredensial Lokal** | Enkripsi terotentikasi AES-256-GCM terintegrasi OS Keyring (Windows DPAPI, macOS Keychain, Linux SecretService) dengan fallback Scrypt. | Malware atau proses lokal dengan hak akses administrator/root. |
| **Integritas Database** | Checksum CRC32 32-bit per-record untuk mendeteksi bit-rot; autentikasi AES-GCM mencegah manipulasi data. Backup otomatis di `data/backups/`. | Kerusakan fisik perangkat keras hard disk yang tidak dapat dipulihkan. |
| **Autentikasi API Key** | Kunci disimpan dalam bentuk salted SHA-256 hash. Kunci mentah hanya ditampilkan sekali saat dibuat dan tidak pernah disimpan dalam plain text. | Kunci API yang tidak sengaja dibagikan atau di-commit ke repositori publik oleh pengguna. |
| **Keamanan Dasbor** | Penegakan ketat loopback (`Host` header validation), validasi origin, token CSRF double-submit, dan session `HttpOnly` `SameSite=Strict`. | Ekstensi peramban pihak ketiga yang memiliki hak inspeksi DOM berlebih. |

---

## 🤝 Kontribusi & Lisensi

Kontribusi kode, pelaporan bug, dan saran perbaikan selalu disambut dengan hangat! Silakan baca [CONTRIBUTING.md](../../CONTRIBUTING.md) untuk panduan standar kontribusi.

Didistribusikan di bawah lisensi terbuka **MIT License**. Lihat [LICENSE](../../LICENSE) untuk rincian lengkap.

Dikembangkan dengan ❤️ oleh **[irhamkaraman](https://github.com/irhamkaraman)**.
