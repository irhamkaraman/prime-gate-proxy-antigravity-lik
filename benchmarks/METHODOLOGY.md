# Prime Gate Benchmark Methodology

Dokumen ini menjelaskan metodologi, lingkungan pengujian, dan instruksi reproduksi untuk mengukur performa latensi, throughput, dan efisiensi memori **Prime Gate Antigravity Proxy**.

---

## 1. Lingkungan Pengujian Standar

- **OS**: Windows 11 (26H2) / Ubuntu 22.04 LTS / macOS 14 Sonoma
- **CPU**: Multi-core modern (x86_64 / ARM64)
- **Runtime**: Python 3.10 - 3.12 (CPython)
- **Database Engine**: SQLite 3.40+ Write-Ahead-Logging (WAL) mode
- **Network Interface**: Local loopback (`127.0.0.1` / `::1`)

---

## 2. Metrik yang Diukur

| Metrik | Satuan | Deskripsi | Target Ideal |
|---|---|---|---|
| **TTFT (Time-To-First-Token)** | ms | Waktu dari request dikirim hingga chunk pertama diterima klien | < 250 ms (upstream dependent) |
| **p50 Latency (Median)** | ms | Latensi rata-rata 50% request | Minimal overhead (< 15 ms di atas upstream) |
| **p95 / p99 Latency** | ms | Latensi pada persentil 95% dan 99% (tail latency) | Menghindari spike durasi akibat locking |
| **Throughput** | req/s | Jumlah request sukses per detik yang diproses gateway | > 50 req/s (lokal) |
| **Exact Cache Lookup** | ms | Waktu pembacaan SQLite WAL untuk query identik | < 5 ms |
| **Semantic Cache Search** | ms | Waktu pencarian cosinus similarity SQLite BLOB | < 20 ms |
| **Compactor Efficiency** | % tokens | Pengurangan payload token prompt pada multi-turn coding | 40% - 70% penghematan |

---

## 3. Tahapan Pengujian (Workflows)

### A. Non-Streaming Raw Latency
Menguji overhead serialisasi/deserialisasi format payload OpenAI (`/v1/chat/completions`) dan Anthropic (`/v1/messages`).

```bash
python benchmarks/benchmark_proxy.py --url http://127.0.0.1:52111 --api-key <YOUR_API_KEY> -n 50 -c 5 --protocol openai
```

### B. Streaming (SSE) & TTFT Measurement
Menguji generator event streaming Server-Sent Events (SSE) dengan pencatatan chunk pertama:

```bash
python benchmarks/benchmark_proxy.py --url http://127.0.0.1:52111 --api-key <YOUR_API_KEY> -n 30 -c 3 --protocol anthropic --stream
```

### C. Output Format Terstruktur (JSON)
Untuk integrasi dengan dashboard CI atau sistem visualisasi benchmark:

```bash
python benchmarks/benchmark_proxy.py --url http://127.0.0.1:52111 --api-key <YOUR_API_KEY> -n 20 -c 2 --json
```

---

## 4. Variabel Pengendali & Sanitasi

1. **Warm-up**: 5 request pemanasan sebelum pengukuran dicatat untuk mengeliminasi inisialisasi koneksi awal (TCP handshake dan JIT overhead).
2. **Koneksi Pool**: Menggunakan shared HTTPX connection pool (`get_shared_client()`) untuk menghindari port exhaustion pada sistem operasi Windows.
3. **Kerahasiaan Kredensial**: Tidak ada data sensitif yang dicatat di log hasil benchmark.
