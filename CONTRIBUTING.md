# Panduan Kontribusi (Contributing Guidelines)

Terima kasih atas minat Anda untuk berkontribusi pada **Prime Gate Antigravity Proxy**! Proyek ini bertujuan menyediakan gateway dual-protocol (OpenAI & Anthropic) yang stabil, aman, dan berkinerja tinggi di atas Google Cloud AI Companion / Antigravity.

---

## 📜 Prinsip Pengembangan & Etika

Untuk menjaga integritas dan keberlanjutan proyek, seluruh kontributor **wajib** mematuhi prinsip berikut:

1. **Kejujuran Teknis & Dokumentasi:**
   - Tidak menggunakan klaim berlebihan atau absolut (misal: "100% aman", "tidak bisa diblokir", dsb).
   - Selalu transparan mengenai risiko penggunaan, keterbatasan teknis, dan model ancaman.
2. **Kepatuhan & Larangan Fitur Eksploitatif:**
   - **DILARANG KERAS** menambahkan fitur yang bertujuan menyamarkan identitas secara manipulatif, mencoba membypass batas kuota upstream, atau mengeksploitasi celah keamanan layanan Google Cloud.
   - Fokus utama pengembangan adalah **keamanan token lokal, stabilitas koneksi, normalisasi protokol, dan efisiensi pengembang**.
3. **Kompatibilitas Mundur (Backward Compatibility):**
   - Semua perubahan pada skema database harus menyertakan skrip migrasi otomatis.
   - Endpoint OpenAI (`/v1/chat/completions`) dan Anthropic (`/v1/messages`, `/v1/messages/count_tokens`) harus tetap mematuhi spesifikasi standar.

---

## 🛠️ Alur Kerja Pengembangan (Workflow)

### 1. Prasyarat Lingkungan
- Python 3.10+
- Node.js 20+ & npm
- Git

### 2. Memulai Kontribusi
1. Fork repository ini di GitHub.
2. Buat branch baru dari `main` dengan format penamaan standar:
   ```bash
   git checkout -b feat/nama-fitur-anda
   # atau
   git checkout -b fix/deskripsi-perbaikan
   ```
3. Install dependensi Python dan UI:
   ```bash
   pip install -r requirements.txt
   cd ui && npm install && cd ..
   ```

### 3. Pengujian Wajib (Testing Discipline)
Setiap kontribusi kode baru atau perbaikan bug **wajib menyertakan pengujian otomatis**. Jangan pernah menurunkan cakupan test yang sudah ada.

- **Jalankan Pengujian Python (Pytest):**
  ```bash
  python -m pytest -v
  ```
- **Kompilasi Frontend (TypeScript & Vite):**
  ```bash
  cd ui
  npm run build
  cd ..
  ```

---

## 📝 Konvensi Pesan Commit (Conventional Commits)

Gunakan format commit standar:
- `feat(scope): deskripsi fitur baru`
- `fix(scope): deskripsi perbaikan bug`
- `docs(scope): pembaruan dokumentasi`
- `refactor(scope): refaktorisasi tanpa perubahan fungsional`
- `test(scope): penambahan atau perbaikan unit test`
- `style(scope): penyesuaian styling atau format UI`

---

## 🛡️ Kebijakan Pelaporan Kerentanan Keamanan (Security)

Jika Anda menemukan kerentanan keamanan (seperti kebocoran kredensial, kelemahan penanganan token OAuth, atau masalah isolasi proses lokal), mohon **TIDAK** membuka public issue di GitHub. Silakan hubungi maintainer secara privat melalui email repository agar perbaikan dapat dipersiapkan secara aman.

---

## 📄 Lisensi

Dengan berkontribusi pada proyek ini, Anda menyetujui bahwa seluruh kontribusi Anda dilisensikan di bawah ketentuan lisensi [MIT License](LICENSE).
