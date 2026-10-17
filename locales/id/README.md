<div align="center">

# ⚡ Prime Gate Antigravity Proxy
### `prime-gate-proxy-antigravity-lik`

**Proxy Gateway Mandiri Standar OpenAI Kompatibel untuk Google Antigravity.**

[![Version](https://img.shields.io/badge/version-1.0.0--beta-38bdf8.svg?style=for-the-badge)](https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Node.js](https://img.shields.io/badge/Node.js-20.x%2B-339933.svg?style=for-the-badge&logo=nodedotjs&logoColor=white)](https://nodejs.org)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](../../LICENSE)

---

### 🌐 Pilih Bahasa / Select Language

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md)

---

</div>

## 📖 Ringkasan

**Prime Gate** adalah jembatan API lokal berperforma tinggi yang membungkus layanan internal Cloud AI Companion / Antigravity dari Google ke dalam protokol **100% kompatibel OpenAI REST & SSE** (`/v1/models`, `/v1/chat/completions`).

Dengan Prime Gate, bosss dapat memanfaatkan kuota Google Antigravity—termasuk **Claude Sonnet 4.6 (Thinking)**, **Claude Opus 4.6 (Thinking)**, dan **Gemini 3.8 Flash**—langsung pada berbagai coding client modern seperti **OpenCode**, **Cursor**, **Continue.dev**, **Aider**, **Cline**, dan **SillyTavern**.

---

## 🌟 Fitur Utama & Keunggulan

1. **100% Kompatibel Standar OpenAI:**
   Pengganti langsung (*drop-in replacement*) untuk setting OpenAI di client mana pun.
2. **Streaming Penalaran Real-Time (Thinking Mode):**
   Mendukung aliran chunk pemikiran model via `delta.reasoning_content` untuk Claude 4.6 Thinking & Gemini 3.8 Flash.
3. **Bebas Error 400 Bad Request (Recursive Schema Sanitizer):**
   Membersihkan skema JSON yang tidak didukung Google Antigravity (`exclusiveMinimum`, `exclusiveMaximum`, `$schema`, `additionalProperties`) agar function/tool calling selalu mulus.
4. **Deteksi Kuota & Tier Akun Cerdas:**
   Mendeteksi otomatis status akun **`Google AI Pro (Trial Tier)`** vs **`Paid Tier`** dan menyajikan katalog model yang tepat.
5. **Web UI Glassmorphic Modern:**
   Dashboard visual Node.js tanpa dependensi eksternal di `http://127.0.0.1:52110` dengan live meter kuota dan sandbox pengujian prompt.
6. **Rich CLI Suite:**
   Perintah terminal lengkap via `rich` & `typer` (`--version`, `quota`, `auth list|import|login`, `daemon start|stop|status`).

---

## ⚡ Panduan Cepat

### 1. Clone & Instalasi
```bash
git clone https://github.com/irhamkaraman/prime-gate-proxy-antigravity-lik.git
cd prime-gate-proxy-antigravity-lik
pip install -r requirements.txt
```
*(Pengguna Windows dapat langsung klik dua kali file `scripts\install.bat`)*

### 2. Jalankan Background Service & Web UI
Jalankan service API dan Web UI sekaligus:
- **Windows (Sekali Klik):**
  ```bash
  scripts\start-all.bat
  ```
- **Atau via CLI Daemon:**
  ```bash
  python -m prime_gate.cli daemon start
  ```
- **Atau Mode Terminal Terpisah:**
  ```bash
  python -m prime_gate.cli start --port 52111
  python -m prime_gate.cli ui --port 52110
  ```

### 3. Buka Web UI Onboarding & Hubungkan Akun
1. Buka browser di **`http://127.0.0.1:52110`**.
2. Jika belum ada akun, layar **Setup Onboarding** bergaya Anthropic akan otomatis tampil:
   - Klik **"Sign in with Google"** untuk login via Google OAuth PKCE.
   - Atau klik **"⚡ Quick Import from OpenCode Config"** untuk mengimpor akun yang sudah tersimpan di OpenCode.
3. Setelah login berhasil, modal otomatis tertutup dan halaman langsung beralih ke **Dasbor Utama**, menampilkan radar kuota real-time dan endpoint OpenAI (`http://127.0.0.1:52111/v1`).

> 💡 **Alternatif Terminal:** Lebih suka via CLI? Anda juga dapat langsung login lewat terminal:
> ```bash
> python -m prime_gate.cli auth login   # Login via browser OAuth
> python -m prime_gate.cli auth import  # Impor config OpenCode
> python -m prime_gate.cli quota        # Tampilkan tabel visual kuota
> ```

---

## 💻 Panduan Perintah CLI

| Perintah | Fungsi |
| :--- | :--- |
| `prime-gate --version` | Menampilkan info versi, runtime, dan codename. |
| `prime-gate quota` | Menampilkan tabel visual kuota dan model yang aktif. |
| `prime-gate check-models` | Memuat otomatis daftar model terkini langsung dari server Google Antigravity. |
| `prime-gate auth list` | Menampilkan seluruh akun Google yang tersimpan. |
| `prime-gate auth import` | Mengimpor akun dari config OpenCode. |
| `prime-gate auth login` | Login akun baru via Google OAuth browser PKCE. |
| `prime-gate auth remove <email>` | Menghapus akun tertentu dari Prime Gate. |
| `prime-gate auth clear` | Menghapus seluruh akun dan mereset ke status onboarding awal. |
| `prime-gate daemon start` | Menjalankan proxy & Web UI di background (headless). |
| `prime-gate daemon status` | Memeriksa PID, port aktif, dan status daemon. |
| `prime-gate daemon stop` | Menghentikan seluruh service background. |
| `prime-gate start` | Menjalankan API server di terminal foreground. |
| `prime-gate ui` | Membuka Web UI dashboard di browser. |

---

## 🔌 Contoh Konfigurasi Client AI

### OpenCode (`~/.config/opencode/opencode.json`)
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
        "gemini-3.1-flash-lite",
        "gpt-oss-120b-medium"
      ]
    }
  }
}
```

---

## 📜 Lisensi & Pembuat

- **Pembuat:** [Irham Karaman](https://github.com/irhamkaraman)
- **Lisensi:** [MIT License](../../LICENSE)
