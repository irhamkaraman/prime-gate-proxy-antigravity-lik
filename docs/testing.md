# Panduan Pengujian & Verifikasi (Testing Guide)

Prime Gate Antigravity Proxy dilengkapi dengan rangkaian pengujian komprehensif untuk memastikan kepatuhan protokol, stabilitas sistem, dan keamanan tingkat tinggi.

---

## 1. Struktur Rangkaian Pengujian

```
tests/
├── conformance/                         # Uji konformansi protokol resmi
│   ├── fixtures/                        # Fixture rekaman agent nyata
│   │   ├── aider_edit_block.json
│   │   ├── claude_code_tool_use.json
│   │   ├── cline_multi_turn.json
│   │   └── cursor_chat_stream.json
│   ├── mock_upstream.py                 # Mock upstream Google Antigravity
│   ├── test_anthropic_conformance.py    # SSE 7-event, delta, thinking, count_tokens
│   └── test_openai_conformance.py       # SSE chunk, tool calling, finish_reason
├── test_stability_and_integration.py    # Failover 429, in-flight cleanup, DB migration
├── test_observability.py                # Prometheus /metrics, /health, X-Request-ID
├── test_api_key_auth.py                 # Constant-time API key verification
├── test_encryption_aes_gcm.py           # AES-256-GCM credentials encryption at-rest
├── test_dashboard_security.py           # CSRF & Host header protection
├── test_websocket_security.py           # WebSocket origin & session token checks
├── test_log_redaction.py                # Otomatisasi redaksi token dan secret di log
├── test_semantic_cache_v3.py            # SQLite WAL cache & cosine vector similarity
└── test_smart_compactor.py              # Pruning riwayat tool output agent
```

---

## 2. Menjalankan Pengujian

### A. Seluruh Test Suite
```bash
pytest -v
```

### B. Uji Konformansi Protokol (Claude Code, Cline, Cursor, Aider)
```bash
pytest -v tests/conformance/
```

### C. Uji Stabilitas, Resiliensi & Integrasi
```bash
pytest -v tests/test_stability_and_integration.py
```

### D. Uji Observabilitas & Metrik
```bash
pytest -v tests/test_observability.py
```

---

## 3. Menambahkan Fixture Baru

Untuk menambahkan rekaman interaksi agent baru ke `tests/conformance/fixtures/`:
1. Simpan rekaman payload dalam format JSON di `tests/conformance/fixtures/<agent_name>_<action>.json`.
2. Format struktur fixture:
```json
{
  "client": "my_agent",
  "protocol": "anthropic",
  "request": {
    "model": "claude-3-7-sonnet",
    "messages": [...]
  },
  "expected_upstream_calls": 1
}
```
3. Tambahkan skenario pengujian di `tests/conformance/test_anthropic_conformance.py` atau `tests/conformance/test_openai_conformance.py`.
