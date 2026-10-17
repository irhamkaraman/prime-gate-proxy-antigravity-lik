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

[🇺🇸 English](../../README.md) • [🇮🇩 Bahasa Indonesia](README.md) • [🇨🇳 简体中文](../zh/README.md) • [🇷🇺 Русский](../ru/README.md) • [🇯🇵 日本語](../ja/README.md) • [🇩🇪 Deutsch](../de/README.md) • [🇫🇷 Français](../fr/README.md) • [📖 Panduan Lengkap](../../docs/USER_GUIDE.md)

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
5. **Dasbor Tailwind CSS v4 Modern dengan Sidebar & Grafik Batang Token:**
   Web UI offline tanpa dependensi eksternal dilengkapi navigasi sidebar rapi, telemetri pemakaian token per detik, menit, jam, hingga harian dengan grafik batang bertumpuk (Chart.js), manajemen akun & meter kuota, playground prompt sandbox, serta diagnostik integritas database binary.
6. **Rich CLI Suite:**
   Perintah terminal lengkap via `rich` & `typer` (`--version`, `quota`, `auth list|import|login|remove|clear`, `db status|check|test-corrupt`, `daemon start|stop|status`).
7. **Database Binary Terkompilasi (Zero Plaintext JSON):**
   Menggantikan penyimpanan JSON plain-text dengan engine binary terkompilasi C (SQLite WAL + Sealed BLOBs). Kredensial akun, token, model, dan kuota dikompresi serta disamarkan dengan verifikasi integritas 32-bit CRC32 tanpa struktur JSON yang bisa dibaca.
8. **Real-Time WebSocket & Database Sentinel Watchdog:**
   Menghubungkan streaming log server dan mutasi data langsung ke dasbor secara real-time via WebSocket (`/ws/live`). Sentinel Watchdog secara kontinu memeriksa integritas data dan langsung membunyikan alert kritis ke terminal dan dasbor jika terdeteksi database corrupt.

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
| `prime-gate auth remove [EMAIL]` | Menghapus akun tertentu (atau memilih interaktif dari menu nomor). |
| `prime-gate auth remove -e <email> -f` | Menghapus akun via flag tanpa konfirmasi (`--email`, `--force`). |
| `prime-gate auth remove -a -f` | Menghapus SEMUA akun via flag tanpa konfirmasi (`--all`, `--force`). |
| `prime-gate delete-account [email]` | Shortcut perintah langsung untuk menghapus akun atau semua akun. |
| `prime-gate auth clear -y` | Menghapus seluruh akun dan mereset ke status onboarding awal. |
| `prime-gate daemon start` | Menjalankan proxy & Web UI di background (headless). |
| `prime-gate daemon status` | Memeriksa PID, port aktif, dan status daemon. |
| `prime-gate daemon stop` | Menghentikan seluruh service background. |
| `prime-gate db check` | Menjalankan audit kriptografis 32-bit CRC32 pada database binary. |
| `prime-gate start` | Menjalankan API server di terminal foreground. |
| `prime-gate ui` | Membuka Web UI dashboard di browser. |

### 🗑️ Panduan Flag Hapus Akun (Terminal & Web UI):
Prime Gate menyediakan fleksibilitas penuh untuk menghapus akun satu per satu maupun sekaligus:
- **Hapus akun spesifik via flag:**
  ```bash
  python -m prime_gate.cli auth remove --email user@gmail.com --force
  # Atau via perintah shortcut:
  python -m prime_gate.cli delete-account -e user@gmail.com -f
  ```
- **Hapus SEMUA akun via flag:**
  ```bash
  python -m prime_gate.cli auth remove --all --force
  ```
- **Pemilihan interaktif:**
  Jalankan `python -m prime_gate.cli auth remove` tanpa argumen untuk memilih dari daftar nomor akun.
- **Di Web UI:**
  Buka tab **Account Manager**, klik tombol merah **"Delete"** pada kartu akun yang ingin dihapus, atau klik **"Delete Account"** pada kartu Active Identity. Untuk menghapus semua, klik **"Clear All"**.

---

## 🔌 Panduan Integrasi Client AI & IDE

Prime Gate menyediakan endpoint standar kompatibel OpenAI di **`http://127.0.0.1:52111/v1`**. Gunakan API Key `prime-gate-proxy` (atau string sembarang).

### 1. Cursor IDE
1. Buka Cursor Settings (**Ctrl+,** atau **Cmd+,**).
2. Masuk ke menu **Features** &gt; **Models**.
3. Pada **OpenAI API Key**, masukkan: `prime-gate-proxy`.
4. Aktifkan saklar **Override OpenAI Base URL** dan isi:
   ```text
   http://127.0.0.1:52111/v1
   ```
5. Di bagian **Add Model**, tambahkan model yang diinginkan:
   - `claude-sonnet-4-6` (Thinking aktif)
   - `gemini-3.8-flash` (Rekomendasi utama harian)
   - `claude-opus-4-6-thinking`

---

### 2. OpenCode (`~/.config/opencode/opencode.json`)
Tambahkan provider `antigravity` pada konfigurasi OpenCode Anda:
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

---

### 3. Continue.dev (`~/.continue/config.json`)
Tambahkan Prime Gate ke daftar `models` di Continue:
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

---

### 4. Cline / Roo Code (Ekstensi VS Code)
1. Buka Pengaturan Cline.
2. Pilih API Provider: **OpenAI Compatible**.
3. Masukkan **Base URL**: `http://127.0.0.1:52111/v1`.
4. Masukkan **API Key**: `prime-gate-proxy`.
5. Masukkan **Model ID**: `claude-sonnet-4-6` atau `gemini-3.8-flash`.

---

### 5. Aider (CLI AI Pair Programmer)
Jalankan Aider langsung mengarah ke endpoint Prime Gate:
```bash
aider --openai-api-base http://127.0.0.1:52111/v1 \
      --openai-api-key prime-gate-proxy \
      --model openai/claude-sonnet-4-6
```

---

### 6. Python OpenAI SDK
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://127.0.0.1:52111/v1",
    api_key="prime-gate-proxy"
)

# Streaming dengan penalaran / thinking
response = client.chat.completions.create(
    model="claude-sonnet-4-6",
    messages=[
        {"role": "user", "content": "Tuliskan kode LRU cache yang aman untuk multi-threading."}
    ],
    stream=True
)

for chunk in response:
    delta = chunk.choices[0].delta
    # Aliran pemikiran (Thinking)
    if hasattr(delta, "reasoning_content") and delta.reasoning_content:
        print(f"[THINKING] {delta.reasoning_content}", end="", flush=True)
    # Aliran teks jawaban
    if delta.content:
        print(delta.content, end="", flush=True)
```

---

### 7. Node.js / TypeScript SDK
```typescript
import OpenAI from "openai";

const client = new OpenAI({
  baseURL: "http://127.0.0.1:52111/v1",
  apiKey: "prime-gate-proxy",
});

async function main() {
  const completion = await client.chat.completions.create({
    model: "gemini-3.8-flash",
    messages: [{ role: "user", content: "Jelaskan arsitektur database binary SQLite WAL." }],
  });

  console.log(completion.choices[0].message.content);
}

main();
```

---

### 8. Uji Coba Cepat via cURL
```bash
curl -X POST http://127.0.0.1:52111/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer prime-gate-proxy" \
  -d '{
    "model": "claude-sonnet-4-6",
    "messages": [{"role": "user", "content": "Halo Prime Gate!"}],
    "stream": false
  }'
```

---

## 🧠 Streaming Penalaran Real-Time (Thinking Mode)

Untuk model dengan kemampuan penalaran mendalam (**Claude Sonnet 4.6**, **Claude Opus 4.6**, dan **Gemini 3.8 Flash**), Prime Gate membedah event internal Google Antigravity dan mengalirkannya via chunk delta standar OpenAI:

```json
{
  "choices": [
    {
      "index": 0,
      "delta": {
        "reasoning_content": "Membedah masalah ke prinsip dasar first-principles..."
      }
    }
  ]
}
```

- **Di Web UI Sandbox:** Blok pemikiran langsung dirender dalam badge khusus `[THINKING] ... [/THINKING]` sebelum jawaban utama dimulai.
- **Di IDE Kompatibel (Cursor/OpenCode):** Pemikiran otomatis muncul di accordion thought boxes.

---

## 🛡️ Database Binary Terkompilasi & Sentinel Watchdog

Berbeda dengan proxy biasa yang menyimpan token dan kredensial di file plaintext `accounts.json`, Prime Gate menggunakan **mesin database binary C terkompilasi** (`data/prime_gate.pgdb`):

- **Nol Plaintext JSON:** Token sensitif dan kuota disimpan sebagai record binary BLOB (`REC_ACCOUNT`, `REC_MODEL`, `REC_QUOTA`).
- **Penyegelan 32-Bit CRC32:** Setiap blok binary dilindungi checksum. Modifikasi heksadesimal luar akan langsung terdeteksi dalam waktu kurang dari 5 detik oleh Sentinel Watchdog.
- **Mode SQLite WAL:** Mendukung throughput tinggi dan konkurensi multi-proses tanpa file-locking.
- **Pipa Event WebSocket (`/ws/live`):** Mutasi database dan log audit dialirkan langsung ke terminal dasbor Web UI.

---

## 📊 Katalog Model & Tier Langganan

| Nama Model | Google AI Pro (Trial Tier) | Google AI Pro (Paid Tier) | Dukungan Thinking |
| :--- | :---: | :---: | :---: |
| **Claude Sonnet 4.6 (Thinking)** | ✅ Tersedia | ❌ Digantikan 5.5 | ✓ Hingga 64k token |
| **Claude Opus 4.6 (Thinking)** | ✅ Tersedia | ❌ Digantikan 5.5 | ✓ Penalaran mendalam |
| **Gemini 3.8 Flash (Rekomendasi)** | ✅ Tersedia | ✅ Tersedia | ✓ Cepat & responsif |
| **Gemini 3.8 Flash High / Med / Low** | ✅ Tersedia | ✅ Tersedia | ✓ Budget pemikiran fleksibel |
| **Gemini 3.1 Flash Lite** | ✅ Tersedia | ✅ Tersedia | Standar |
| **GPT-OSS 120B (Medium)** | ✅ Tersedia | ✅ Tersedia | Standar |
| **Claude Sonnet 5.5 (Thinking)** | ❌ Khusus Berbayar | ✅ Tersedia | ✓ Extended thinking |
| **Gemini 4 Argon (Low)** | ❌ Khusus Berbayar | ✅ Tersedia | Standar |

> ⚠️ **Catatan Gemini 2.5:** Model lama `gemini-2.5-pro` dan `gemini-2.5-flash` telah dihapus dari katalog karena server Google sering mengalami kehabisan kapasitas (`503 Service Unavailable: MODEL_CAPACITY_EXHAUSTED`). Gunakan **`gemini-3.8-flash`** atau **`claude-sonnet-4-6`**.

---

## ❓ Tanya Jawab & Solusi Kendala (FAQ)

### 1. Error "503 Service Unavailable: MODEL_CAPACITY_EXHAUSTED"
- **Penyebab:** Upstream Google kelebihan beban pada model legacy Gemini 2.5.
- **Solusi:** Beralih ke `gemini-3.8-flash` atau `claude-sonnet-4-6`.

### 2. Error "Errno 10048: Only one usage of each socket address is normally permitted"
- **Penyebab:** Port 52111 atau 52110 sedang digunakan proses lain / instance sebelumnya.
- **Solusi:** Matikan daemon lama dengan `prime-gate daemon stop`, atau jalankan dengan port baru: `prime-gate start --port 52120`.

### 3. Di mana kredensial akun disimpan?
- **Jawaban:** Tersimpan di file binary `data/prime_gate.pgdb`. File ini sudah otomatis dimasukkan ke `.gitignore` sehingga **tidak akan pernah bocor ke GitHub**.

---

## 📜 Lisensi & Pembuat

- **Pembuat:** [Irham Karaman](https://github.com/irhamkaraman)
- **Lisensi:** [MIT License](../../LICENSE)
