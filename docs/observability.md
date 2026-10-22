# Panduan Observabilitas & Monitoring (Observability Guide)

Prime Gate Antigravity Proxy menyediakan visibilitas tingkat produksi melalui metrik standar Prometheus, probe kesiapan (readiness) dan kelangsungan (liveness), pelacakan terdistribusi (`X-Request-ID`), serta logging terstruktur.

---

## 1. Prometheus Metrics (`/metrics`)

Endpoint `/metrics` mengekspos metrik runtime dalam format OpenMetrics/Prometheus standar (`text/plain; version=0.0.4; charset=utf-8`).

### Daftar Metrik Utama

| Metrik | Tipe | Label | Deskripsi |
|---|---|---|---|
| `primegate_requests_total` | Counter | `protocol`, `model`, `status` | Total request proxy yang diproses |
| `primegate_request_duration_seconds` | Histogram | `protocol`, `model` | Distribusi durasi pemrosesan request (latensi) |
| `primegate_time_to_first_token_seconds` | Histogram | `protocol`, `model` | Waktu hingga chunk token pertama pada streaming (TTFT) |
| `primegate_tokens_total` | Counter | `type` (`prompt`, `completion`, `reasoning`, `saved`) | Akumulasi konsumsi dan penghematan token |
| `primegate_cache_hits_total` | Counter | `type` (`exact`, `semantic`) | Total kejadian cache hit |
| `primegate_cache_misses_total` | Counter | - | Total kejadian cache miss |
| `primegate_active_accounts` | Gauge | - | Jumlah akun upstream aktif dan terautentikasi |
| `primegate_account_failovers_total` | Counter | - | Total perpindahan akun otomatis akibat 429/503 |
| `primegate_compactor_tokens_saved_total`| Counter | - | Total token prompt yang dihemat oleh Context Compactor |

### Konfigurasi Prometheus Scraper (`prometheus.yml`)

```yaml
scrape_configs:
  - job_name: "primegate-proxy"
    scrape_interval: 10s
    static_configs:
      - targets: ["localhost:52111"]
```

---

## 2. Health & Readiness Probes

### A. General Health (`/health` atau `/v1/health`)
Mengembalikan ringkasan status operasional, database SQLite WAL, model health, dan snapshot telemetri.

### B. Kubernetes Liveness Probe (`/health/liveness`)
Memverifikasi bahwa proses proxy berjalan dan mampu merespons request.
- Status Code: `200 OK`
```json
{
  "status": "ok",
  "uptime_seconds": 12450,
  "pid": 3812
}
```

### C. Kubernetes Readiness Probe (`/health/readiness`)
Memverifikasi bahwa minimal satu akun upstream terkonfigurasi dan database WAL dapat ditulis.
- Status Code: `200 OK` (jika siap menerima traffic) atau `503 Service Unavailable`
```json
{
  "status": "ready",
  "active_accounts": 2,
  "db_wal_writable": true
}
```

---

## 3. Distributed Tracing (`X-Request-ID`)

Setiap request masuk akan diperiksa untuk header `X-Request-ID` (atau `x-request-id`):
- Jika klien menyediakannya, identifier tersebut akan divalidasi dan diteruskan.
- Jika tidak ada, proxy akan secara otomatis menghasilkan identifier acak `UUIDv4`.
- Header `X-Request-ID` selalu disertakan dalam setiap respons HTTP dan dicatat dalam tabel `pg_request_logs` untuk mempermudah korelasi log.

---

## 4. Structured JSON Logging

Prime Gate mendukung logging JSON untuk integrasi langsung dengan log aggregator (Loki, Datadog, ELK).

### Mengaktifkan JSON Logging
Set environment variable:
```bash
export LOG_FORMAT=json
# Windows PowerShell
$env:LOG_FORMAT = "json"
```

Contoh output:
```json
{
  "timestamp": "2026-10-23T00:15:20.124Z",
  "level": "INFO",
  "logger": "prime_gate.server",
  "request_id": "c1f7a0b3e5124b89",
  "message": "Processed /v1/messages for claude-3-7-sonnet in 184.2ms [200 OK]"
}
```

> [!NOTE]
> Semua log secara otomatis disaring oleh engine `Redactor` untuk memastikan token autentikasi (Google OAuth, Bearer token, Prime Gate API keys) tidak pernah tercetak secara mentah.
