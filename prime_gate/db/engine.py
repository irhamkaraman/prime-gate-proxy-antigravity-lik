import os
import time
import json
import sqlite3
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

from .binary_codec import (
    BinaryCodec, DatabaseCorruptedError,
    REC_ACCOUNT, REC_MODEL, REC_QUOTA, REC_SYSTEM, REC_LOG
)
from .events import event_bus
import struct
import shutil
from ..crypto.key_manager import KeyManager
from ..crypto.auth_manager import AuthManager

logger = logging.getLogger("prime_gate.db.engine")

class BinaryDatabaseEngine:
    """
    SQLite WAL database engine for Prime Gate.
    Stores sensitive accounts, models, quotas, and telemetry as binary-obfuscated BLOBs
    using SQLite in Write-Ahead-Logging (WAL) mode to avoid plaintext credential storage on disk.
    
    Key Properties:
    - Eliminates plaintext JSON or credentials in local file storage via binary obfuscation.
    - Fast query performance with SQLite Write-Ahead Logging (WAL) concurrency.
    - Automatic 32-bit CRC32 checksum verification on every record read for storage integrity checking (not cryptographic encryption).
    - Instant real-time WebSocket alert and incident log on data corruption.
    """

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            # Default to data/prime_gate.pgdb inside project root
            base_dir = Path(__file__).resolve().parent.parent.parent / "data"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.db_path = base_dir / "prime_gate.pgdb"
        else:
            self.db_path = Path(db_path)
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
                isolation_level=None  # autocommit mode for high-throughput concurrency
            )
            self._conn.row_factory = sqlite3.Row
            # Configure high-performance compiled binary engine pragmas
            self._conn.execute("PRAGMA journal_mode = WAL;")
            self._conn.execute("PRAGMA synchronous = NORMAL;")
            self._conn.execute("PRAGMA page_size = 4096;")
            self._conn.execute("PRAGMA temp_store = MEMORY;")
            self._conn.execute("PRAGMA mmap_size = 268435456;")  # 256MB memory-mapped I/O
        return self._conn

    def _init_db(self):
        """Initializes tables for binary records and incident audit ledger."""
        conn = self._get_connection()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_records (
                key TEXT PRIMARY KEY,
                record_type INTEGER NOT NULL,
                data BLOB NOT NULL,
                crc32 INTEGER NOT NULL,
                updated_at REAL NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_incidents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                severity TEXT NOT NULL,
                event_type TEXT NOT NULL,
                target_key TEXT,
                message TEXT NOT NULL,
                details TEXT,
                created_at REAL NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT NOT NULL,
                timestamp REAL NOT NULL,
                account_email TEXT,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                latency_ms REAL NOT NULL DEFAULT 0.0,
                status_code INTEGER NOT NULL DEFAULT 200,
                stream INTEGER NOT NULL DEFAULT 0,
                quota_snapshot TEXT,
                created_at REAL NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_semantic_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_key TEXT UNIQUE NOT NULL,
                prompt_hash TEXT NOT NULL,
                prompt_preview TEXT NOT NULL,
                response_text TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                reasoning_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                hit_count INTEGER NOT NULL DEFAULT 0,
                tokens_saved_total INTEGER NOT NULL DEFAULT 0,
                created_at REAL NOT NULL,
                last_hit_at REAL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_key ON pg_semantic_cache(cache_key);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_model ON pg_semantic_cache(model);")

        # Idempotent column migrations for pg_semantic_cache
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN embedding BLOB;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN tools_signature TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN scope TEXT NOT NULL DEFAULT 'default';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN context_hash TEXT NOT NULL DEFAULT '';")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN embedding_model TEXT;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN embedding_dim INTEGER;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_semantic_cache ADD COLUMN expires_at REAL;")
        except Exception:
            pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_scope_ctx ON pg_semantic_cache(scope, context_hash, model);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON pg_semantic_cache(expires_at);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_cache_verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cache_id INTEGER,
                timestamp REAL NOT NULL,
                cache_type TEXT NOT NULL,
                similarity_score REAL NOT NULL,
                upstream_similarity REAL,
                is_false_hit INTEGER NOT NULL DEFAULT 0,
                details TEXT
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_verify_time ON pg_cache_verifications(timestamp DESC);")

        # Idempotent column migrations for pg_request_logs
        try:
            conn.execute("ALTER TABLE pg_request_logs ADD COLUMN cache_hit INTEGER NOT NULL DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_request_logs ADD COLUMN tokens_saved INTEGER NOT NULL DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_request_logs ADD COLUMN cache_hit_type INTEGER NOT NULL DEFAULT 0;")
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE pg_request_logs ADD COLUMN similarity_score REAL NOT NULL DEFAULT 0.0;")
        except Exception:
            pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_req_timestamp ON pg_request_logs(timestamp DESC);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_req_model ON pg_request_logs(model);")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_req_account ON pg_request_logs(account_email);")

        # Autonomous Zero-Touch Auto-Update Audit Ledger
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_auto_update_ledger (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                triggered_at REAL NOT NULL,
                status TEXT NOT NULL,
                from_commit TEXT,
                to_commit TEXT,
                from_version TEXT,
                to_version TEXT,
                ui_rebuilt INTEGER DEFAULT 0,
                log TEXT,
                created_at REAL NOT NULL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_update_ledger_time ON pg_auto_update_ledger(created_at DESC);")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                prefix TEXT NOT NULL,
                key_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at REAL NOT NULL,
                last_used_at REAL,
                revoked_at REAL
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_api_keys_revoked ON pg_api_keys(revoked_at);")

        # Idempotent column migrations for pg_api_keys (Fase 5.1 Client Policy Enforcement)
        api_key_cols = [
            ("rate_limit_rpm", "INTEGER NOT NULL DEFAULT 0"),
            ("rate_limit_tpd", "INTEGER NOT NULL DEFAULT 0"),
            ("quota_credits", "REAL NOT NULL DEFAULT 0.0"),
            ("allowed_models", "TEXT NOT NULL DEFAULT '[]'"),
            ("cache_scope", "TEXT NOT NULL DEFAULT 'shared'")
        ]
        for col_name, col_type in api_key_cols:
            try:
                conn.execute(f"ALTER TABLE pg_api_keys ADD COLUMN {col_name} {col_type};")
            except Exception:
                pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS pg_api_key_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key_id INTEGER NOT NULL,
                prompt_tokens INTEGER NOT NULL DEFAULT 0,
                completion_tokens INTEGER NOT NULL DEFAULT 0,
                total_tokens INTEGER NOT NULL DEFAULT 0,
                model TEXT NOT NULL,
                created_at REAL NOT NULL,
                FOREIGN KEY (key_id) REFERENCES pg_api_keys(id) ON DELETE CASCADE
            );
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_key_usage_time ON pg_api_key_usage(key_id, created_at);")

        # Auto-migrate legacy V1 records to V2 AES-256-GCM
        try:
            self.migrate_v1_to_v2()
        except Exception as e:
            logger.warning(f"V1 to V2 migration check deferred: {e}")

        logger.info(f"Binary Database Engine initialized at: {self.db_path} (WAL Mode enabled)")

    def set(self, key: str, payload: Dict[str, Any], record_type: int = REC_SYSTEM) -> bool:
        """Packs payload into sealed binary BLOB and writes to database."""
        try:
            blob = BinaryCodec.pack(record_type, payload, key_name=key)
            # Extract CRC32 from packed header for secondary indexing
            _, _, _, _, stored_crc, _ = BinaryCodec.extract_header(blob)
            now = time.time()

            conn = self._get_connection()
            conn.execute("""
                INSERT INTO pg_records (key, record_type, data, crc32, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    record_type = excluded.record_type,
                    data = excluded.data,
                    crc32 = excluded.crc32,
                    updated_at = excluded.updated_at
            """, (key, record_type, blob, stored_crc, now))

            event_bus.notify_mutation("SET", key, record_type)
            return True
        except Exception as e:
            logger.error(f"Failed to store binary record '{key}': {e}")
            return False

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves and unpacks a binary record.
        If data corruption or CRC32 mismatch is detected, logs critical error,
        notifies active WebSockets, records an incident, and raises DatabaseCorruptedError.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT data, record_type, crc32 FROM pg_records WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            return None

        blob = row["data"]
        try:
            record_type, payload, ts = BinaryCodec.unpack(blob, key_name=key)
            return payload
        except DatabaseCorruptedError as e:
            self._handle_corruption(key, str(e), e.details)
            raise e
        except Exception as e:
            err_msg = f"Unexpected decode failure on key '{key}': {e}"
            self._handle_corruption(key, err_msg, {"error": str(e)})
            raise DatabaseCorruptedError(err_msg, key=key)

    def delete(self, key: str) -> bool:
        """Deletes a record by key."""
        conn = self._get_connection()
        cursor = conn.execute("DELETE FROM pg_records WHERE key = ?", (key,))
        if cursor.rowcount > 0:
            event_bus.notify_mutation("DELETE", key, 0)
            return True
        return False

    def list_keys(self, prefix: str = "") -> List[str]:
        """Lists all stored keys, optionally filtered by prefix."""
        conn = self._get_connection()
        if prefix:
            cursor = conn.execute("SELECT key FROM pg_records WHERE key LIKE ? ORDER BY key", (f"{prefix}%",))
        else:
            cursor = conn.execute("SELECT key FROM pg_records ORDER BY key")
        return [row["key"] for row in cursor.fetchall()]

    def get_all(self, prefix: str = "") -> Dict[str, Dict[str, Any]]:
        """Retrieves and unpacks all records matching prefix."""
        keys = self.list_keys(prefix)
        results = {}
        for k in keys:
            try:
                val = self.get(k)
                if val is not None:
                    results[k] = val
            except DatabaseCorruptedError:
                # Corrupted record handled and logged, skip to next
                continue
        return results

    def run_integrity_check(self) -> Dict[str, Any]:
        """
        Runs comprehensive full-database integrity audit:
        1. SQLite compiled B-Tree & page level checks (PRAGMA integrity_check)
        2. Block-level CRC32 checksum and unmasking on every binary record
        """
        conn = self._get_connection()
        # 1. SQLite Engine Check
        sqlite_res = conn.execute("PRAGMA integrity_check;").fetchall()
        sqlite_status = [row[0] for row in sqlite_res]
        sqlite_ok = (sqlite_status == ["ok"])

        # 2. Block-level Record Check
        cursor = conn.execute("SELECT key, record_type, data, crc32 FROM pg_records")
        rows = cursor.fetchall()

        scanned = 0
        corruptions = []

        for row in rows:
            scanned += 1
            key = row["key"]
            blob = row["data"]
            try:
                BinaryCodec.unpack(blob, key_name=key)
            except DatabaseCorruptedError as e:
                corruptions.append({
                    "key": key,
                    "error": str(e),
                    "details": e.details
                })
                self._handle_corruption(key, str(e), e.details)

        is_healthy = sqlite_ok and (len(corruptions) == 0)
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0

        event_bus.notify_health(
            status="HEALTHY" if is_healthy else "CORRUPTED",
            size_bytes=size_bytes,
            record_count=scanned,
            integrity_ok=is_healthy
        )

        return {
            "healthy": is_healthy,
            "sqlite_status": sqlite_status,
            "records_scanned": scanned,
            "corruptions_count": len(corruptions),
            "corruptions": corruptions,
            "size_bytes": size_bytes,
            "db_path": str(self.db_path)
        }

    def simulate_corruption(self, key: str) -> bool:
        """
        Simulates database corruption by intentionally tampering with the binary bytes
        of the specified record. Useful for live WebSocket testing and sentinel verification.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT data FROM pg_records WHERE key = ?", (key,))
        row = cursor.fetchone()
        if not row:
            logger.warning(f"Cannot simulate corruption: Key '{key}' not found.")
            return False

        original_blob = bytearray(row["data"])
        if len(original_blob) > 28:
            # Flip bits in the payload past the header
            original_blob[-5] ^= 0xFF
            original_blob[-6] ^= 0xAA

        conn.execute("UPDATE pg_records SET data = ? WHERE key = ?", (bytes(original_blob), key))
        logger.warning(f"Simulated binary corruption injected into record '{key}'!")

        # Attempt to read it immediately to trigger corruption handlers
        try:
            self.get(key)
        except DatabaseCorruptedError:
            pass
        return True

    def _handle_corruption(self, key: str, reason: str, details: Dict[str, Any]):
        """Triggered upon any corruption detection: logs critical alert, writes incident, and notifies WebSockets."""
        logger.critical(f"[CRITICAL] [DATABASE_CORRUPT] Critical corruption detected in record '{key}': {reason}")
        
        # Record incident in database if possible
        try:
            conn = self._get_connection()
            import json
            conn.execute("""
                INSERT INTO pg_incidents (severity, event_type, target_key, message, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, ("CRITICAL", "CORRUPTION_DETECTED", key, reason, json.dumps(details), time.time()))
        except Exception:
            pass

        # Broadcast immediately to all connected WebSocket clients
        event_bus.notify_corruption(key=key, reason=reason, details=details)

    def get_incidents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns recent incident reports recorded by Database Sentinel (newest first)."""
        conn = self._get_connection()
        cursor = conn.execute(
            "SELECT id, severity, event_type, target_key, message, details, created_at FROM pg_incidents ORDER BY id DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        return [
            {
                "id": r["id"],
                "severity": r["severity"],
                "event_type": r["event_type"],
                "target_key": r["target_key"],
                "message": r["message"],
                "scope": r["scope"] if "scope" in r.keys() else "default",
                "context_hash": r["context_hash"] if "context_hash" in r.keys() else "",
                "expires_at": r["expires_at"] if "expires_at" in r.keys() else None,
                "created_at": r["created_at"],
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"]))
            }
            for r in rows
        ]

    def get_status(self) -> Dict[str, Any]:
        """Returns database operational status and size metrics."""
        size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
        conn = self._get_connection()
        count_records = conn.execute("SELECT COUNT(*) FROM pg_records").fetchone()[0]
        count_incidents = conn.execute("SELECT COUNT(*) FROM pg_incidents").fetchone()[0]

        return {
            "engine": "Compiled C Binary (SQLite WAL + Sealed BLOBs)",
            "format": "PGDB v1 (CRC32 Checksummed)",
            "db_path": str(self.db_path),
            "size_bytes": size_bytes,
            "records_count": count_records,
            "incidents_count": count_incidents,
            "active_ws_subscribers": event_bus.subscriber_count,
            "recent_incidents": self.get_incidents(limit=5)
        }

    def optimize_database(self) -> Dict[str, Any]:
        """Runs SQLite PRAGMA wal_checkpoint(TRUNCATE) and VACUUM to reclaim space and optimize B-Tree pages."""
        conn = self._get_connection()
        try:
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            conn.execute("VACUUM;")
            size_bytes = self.db_path.stat().st_size if self.db_path.exists() else 0
            return {
                "success": True,
                "healthy": True,
                "message": "VACUUM and WAL checkpoint (TRUNCATE) completed successfully.",
                "size_bytes": size_bytes
            }
        except Exception as e:
            logger.error(f"Failed to vacuum/optimize database: {e}")
            return {
                "success": False,
                "healthy": False,
                "error": str(e)
            }

    def record_request_hit(
        self,
        request_id: str,
        timestamp: float,
        account_email: Optional[str],
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int = 0,
        latency_ms: float = 0.0,
        status_code: int = 200,
        stream: int = 0,
        quota_snapshot: Optional[Any] = None,
        cache_hit: int = 0,
        tokens_saved: int = 0,
        cache_hit_type: int = 0,
        similarity_score: float = 0.0,
        key_id: Optional[int] = None
    ) -> bool:
        """Records a granular API request hit into the persistent database ledger."""
        try:
            total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
            now = time.time()

            if key_id is not None and key_id > 0:
                try:
                    self.record_api_key_tokens(key_id, prompt_tokens, completion_tokens, model)
                except Exception as ex:
                    logger.debug(f"Could not record key tokens: {ex}")
            quota_json = None
            if quota_snapshot is not None:
                if isinstance(quota_snapshot, str):
                    quota_json = quota_snapshot
                else:
                    quota_json = json.dumps(quota_snapshot)

            conn = self._get_connection()
            conn.execute("""
                INSERT INTO pg_request_logs (
                    request_id, timestamp, account_email, model,
                    prompt_tokens, completion_tokens, reasoning_tokens, total_tokens,
                    latency_ms, status_code, stream, quota_snapshot, created_at,
                    cache_hit, tokens_saved, cache_hit_type, similarity_score
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                request_id, timestamp or now, account_email, model,
                prompt_tokens, completion_tokens, reasoning_tokens, total_tokens,
                latency_ms, status_code, stream, quota_json, now,
                cache_hit, tokens_saved, cache_hit_type, similarity_score
            ))
            event_bus.notify_mutation("REQUEST_HIT", request_id, 0)

            # Record into Prometheus metrics collector
            try:
                from ..metrics import metrics
                proto = "anthropic" if (request_id and request_id.startswith("msg_")) else "openai"
                metrics.record_request(
                    protocol=proto,
                    model=model,
                    status=status_code,
                    duration_seconds=latency_ms / 1000.0,
                    ttft_seconds=(latency_ms / 1000.0) if stream else None
                )
                metrics.record_tokens(
                    prompt=prompt_tokens,
                    completion=completion_tokens,
                    reasoning=reasoning_tokens,
                    saved=tokens_saved
                )
                if cache_hit:
                    metrics.record_cache_hit("exact" if cache_hit_type == 1 else "semantic")
                else:
                    metrics.record_cache_miss()
            except Exception:
                pass

            return True
        except Exception as e:
            logger.error(f"Failed to record request hit for '{request_id}': {e}")
            return False

    def get_model_benchmarks(self) -> Dict[str, Any]:
        """
        Computes benchmark metrics, token consumption rankings, latency benchmarks,
        cache savings, and quota impact scores per model across all historical hits.
        """
        conn = self._get_connection()
        total_tokens_all = conn.execute("SELECT SUM(total_tokens) FROM pg_request_logs").fetchone()[0] or 0
        total_requests_all = conn.execute("SELECT COUNT(*) FROM pg_request_logs").fetchone()[0] or 0
        total_cache_hits = conn.execute("SELECT COUNT(*) FROM pg_request_logs WHERE cache_hit = 1").fetchone()[0] or 0
        total_tokens_saved = conn.execute("SELECT SUM(tokens_saved) FROM pg_request_logs WHERE cache_hit = 1").fetchone()[0] or 0

        cursor = conn.execute("""
            SELECT
                model,
                COUNT(*) as req_count,
                SUM(prompt_tokens) as total_prompt,
                SUM(completion_tokens) as total_completion,
                SUM(reasoning_tokens) as total_reasoning,
                SUM(total_tokens) as total_tokens,
                SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) as cache_hits,
                SUM(tokens_saved) as tokens_saved,
                AVG(latency_ms) as avg_latency,
                MIN(latency_ms) as min_latency,
                MAX(latency_ms) as max_latency,
                MAX(timestamp) as last_seen
            FROM pg_request_logs
            GROUP BY model
            ORDER BY total_tokens DESC
        """)
        rows = cursor.fetchall()

        benchmarks = []
        for r in rows:
            m_total = r["total_tokens"] or 0
            m_prompt = r["total_prompt"] or 0
            m_comp = r["total_completion"] or 0
            m_think = r["total_reasoning"] or 0
            m_reqs = r["req_count"] or 0
            m_hits = r["cache_hits"] or 0
            m_saved = r["tokens_saved"] or 0
            avg_lat = round(r["avg_latency"] or 0.0, 1)

            share_pct = round((m_total / total_tokens_all * 100), 2) if total_tokens_all > 0 else 0.0
            
            # Throughput estimate: tokens per second during generation
            tok_per_sec = 0.0
            if avg_lat > 0 and m_comp > 0:
                tok_per_sec = round((m_comp / (avg_lat / 1000.0)), 1)

            # Quota impact score based on token volume & model weight (Claude/GPT weigh more)
            model_lower = r["model"].lower()
            tier_multiplier = 1.0
            if "claude" in model_lower or "opus" in model_lower:
                tier_multiplier = 3.0
            elif "gpt" in model_lower:
                tier_multiplier = 2.0
            
            quota_score = round(share_pct * tier_multiplier, 1)

            benchmarks.append({
                "model": r["model"],
                "requests_count": m_reqs,
                "total_tokens": m_total,
                "prompt_tokens": m_prompt,
                "completion_tokens": m_comp,
                "reasoning_tokens": m_think,
                "cache_hits": m_hits,
                "tokens_saved": m_saved,
                "avg_latency_ms": avg_lat,
                "min_latency_ms": round(r["min_latency"] or 0.0, 1),
                "max_latency_ms": round(r["max_latency"] or 0.0, 1),
                "tokens_per_second": tok_per_sec,
                "token_share_pct": share_pct,
                "quota_impact_score": quota_score,
                "last_seen_ts": r["last_seen"],
                "last_seen_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["last_seen"])) if r["last_seen"] else "N/A"
            })

        usd_saved = round((total_tokens_saved * 0.000005), 2)
        idr_saved = int(usd_saved * 16250)
        total_usd_val = round((total_tokens_all * 0.000005), 2)
        total_idr_val = int(total_usd_val * 16250)

        return {
            "total_models_tracked": len(benchmarks),
            "total_requests": total_requests_all,
            "total_tokens": total_tokens_all,
            "total_cache_hits": total_cache_hits,
            "total_tokens_saved": total_tokens_saved,
            "usd_value_saved": usd_saved,
            "idr_value_saved": idr_saved,
            "total_usd_delivered": total_usd_val,
            "total_idr_delivered": total_idr_val,
            "top_spender_model": benchmarks[0]["model"] if benchmarks else None,
            "models": benchmarks
        }

    def get_request_logs(
        self,
        limit: int = 50,
        offset: int = 0,
        model: Optional[str] = None,
        account: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves paginated and filtered list of granular request hits."""
        conn = self._get_connection()
        query = "SELECT * FROM pg_request_logs WHERE 1=1"
        params = []

        if model:
            query += " AND model = ?"
            params.append(model)
        if account:
            query += " AND account_email = ?"
            params.append(account)

        # Count total
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total_count = conn.execute(count_query, params).fetchone()[0]

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        logs = []
        for r in rows:
            quota_obj = None
            if r["quota_snapshot"]:
                try:
                    quota_obj = json.loads(r["quota_snapshot"])
                except Exception:
                    quota_obj = r["quota_snapshot"]

            row_keys = r.keys()
            cache_hit_val = bool(r["cache_hit"]) if "cache_hit" in row_keys else False
            tokens_saved_val = (r["tokens_saved"] or 0) if "tokens_saved" in row_keys else 0
            cache_hit_type_val = int(r["cache_hit_type"]) if "cache_hit_type" in row_keys else (1 if cache_hit_val else 0)
            similarity_score_val = round(float(r["similarity_score"]), 3) if "similarity_score" in row_keys and r["similarity_score"] else 0.0

            logs.append({
                "id": r["id"],
                "request_id": r["request_id"],
                "timestamp": r["timestamp"],
                "time_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["timestamp"])),
                "account_email": r["account_email"] or "default",
                "model": r["model"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "reasoning_tokens": r["reasoning_tokens"],
                "total_tokens": r["total_tokens"],
                "latency_ms": round(r["latency_ms"], 1),
                "status_code": r["status_code"],
                "stream": bool(r["stream"]),
                "quota_snapshot": quota_obj,
                "cache_hit": cache_hit_val,
                "tokens_saved": tokens_saved_val,
                "cache_hit_type": cache_hit_type_val,
                "similarity_score": similarity_score_val
            })

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "logs": logs
        }

    # =========================================================================
    # Semantic & Prompt Caching Layer
    # =========================================================================

    def get_cache_config(self) -> Dict[str, Any]:
        """Retrieves current Smart Cache, Compactor & Sentinel configuration."""
        cfg = self.get("cache:config")
        default_model = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
        if not cfg or not isinstance(cfg, dict):
            return {
                "enabled": True,
                "bypass_tools": False,
                "semantic_enabled": True,
                "semantic_agent_enabled": False,
                "semantic_threshold": 0.93,
                "semantic_threshold_chat": 0.93,
                "semantic_threshold_agent": 0.96,
                "embedding_model": default_model,
                "max_entries": 5000,
                "verification_sampling_enabled": False,
                "verification_sampling_rate": 0.05,
                "cache_mode": "hybrid",
                "turn_based_keying": True,
                "min_prompt_length": 5,
                "ttl_seconds": 86400,
                "compactor_enabled": True,
                "compactor_window_turns": 3,
                "compactor_window_tools": 2,
                "compactor_max_chars": 600,
                "compactor_dry_run": False,
                "compactor_preserve_errors": True,
                "compactor_preserve_re_references": True,
                "compactor_client_overrides": {},
                "compactor_model_overrides": {},
                "loop_guard_enabled": True,
                "loop_guard_max_repeats": 3,
            }
        return {
            "enabled": bool(cfg.get("enabled", True)),
            "bypass_tools": bool(cfg.get("bypass_tools", False)),
            "semantic_enabled": bool(cfg.get("semantic_enabled", True)),
            "semantic_agent_enabled": bool(cfg.get("semantic_agent_enabled", False)),
            "semantic_threshold": float(cfg.get("semantic_threshold", 0.93)),
            "semantic_threshold_chat": float(cfg.get("semantic_threshold_chat", cfg.get("semantic_threshold", 0.93))),
            "semantic_threshold_agent": float(cfg.get("semantic_threshold_agent", 0.96)),
            "embedding_model": str(cfg.get("embedding_model", default_model)),
            "max_entries": int(cfg.get("max_entries", 5000)),
            "verification_sampling_enabled": bool(cfg.get("verification_sampling_enabled", False)),
            "verification_sampling_rate": float(cfg.get("verification_sampling_rate", 0.05)),
            "cache_mode": str(cfg.get("cache_mode", "hybrid")),
            "turn_based_keying": bool(cfg.get("turn_based_keying", True)),
            "min_prompt_length": int(cfg.get("min_prompt_length", 5)),
            "ttl_seconds": int(cfg.get("ttl_seconds", 86400)),
            "compactor_enabled": bool(cfg.get("compactor_enabled", True)),
            "compactor_window_turns": int(cfg.get("compactor_window_turns", 3)),
            "compactor_window_tools": int(cfg.get("compactor_window_tools", 2)),
            "compactor_max_chars": int(cfg.get("compactor_max_chars", 600)),
            "compactor_dry_run": bool(cfg.get("compactor_dry_run", False)),
            "compactor_preserve_errors": bool(cfg.get("compactor_preserve_errors", True)),
            "compactor_preserve_re_references": bool(cfg.get("compactor_preserve_re_references", True)),
            "compactor_client_overrides": cfg.get("compactor_client_overrides") if isinstance(cfg.get("compactor_client_overrides"), dict) else {},
            "compactor_model_overrides": cfg.get("compactor_model_overrides") if isinstance(cfg.get("compactor_model_overrides"), dict) else {},
            "loop_guard_enabled": bool(cfg.get("loop_guard_enabled", True)),
            "loop_guard_max_repeats": int(cfg.get("loop_guard_max_repeats", 3)),
        }

    def record_compactor_tokens_saved(self, tokens: int) -> int:
        """Accumulates saved tokens from Context Compactor."""
        if tokens <= 0:
            return int(self.get("telemetry:compactor_tokens_saved_total") or 0)
        curr = int(self.get("telemetry:compactor_tokens_saved_total") or 0)
        new_total = curr + tokens
        self.set("telemetry:compactor_tokens_saved_total", new_total)
        try:
            from ..metrics import metrics
            metrics.record_compactor_saved(tokens)
        except Exception:
            pass
        return new_total

    def get_compactor_stats(self) -> Dict[str, Any]:
        """Returns cumulative compactor statistics for dashboard telemetry."""
        total_tokens = int(self.get("telemetry:compactor_tokens_saved_total") or 0)
        return {
            "compactor_tokens_saved_total": total_tokens,
        }

    def set_cache_config(self, config: Dict[str, Any]) -> bool:
        """Saves Smart Cache configuration and syncs vector embedding model if changed."""
        current = self.get_cache_config()
        old_model = current.get("embedding_model")
        current.update(config)
        new_model = current.get("embedding_model")
        if new_model and new_model != old_model:
            try:
                from prime_gate.cache.semantic import SemanticVectorEngine
                SemanticVectorEngine.set_model_name(new_model)
                dim = SemanticVectorEngine.get_embedding_dimension()
                self.verify_or_rebuild_vector_index(new_model, dim)
            except Exception as e:
                logger.warning(f"Vector model sync failed: {e}")

        success = self.set("cache:config", current)
        event_bus.notify_mutation("CACHE_CONFIG", "cache:config", 0)
        return success

    # =========================================================================
    # Autonomous Zero-Touch Auto-Update Configuration & Audit Ledger
    # =========================================================================

    DEFAULT_AUTO_UPDATE_CONFIG: Dict[str, Any] = {
        "enabled": True,                 # Autonomous zero-touch sync enabled by default
        "check_interval_seconds": 600,   # Check every 10 minutes (600s)
        "idle_threshold_seconds": 30,    # Require 30s of 0 in-flight traffic before pulling
        "auto_rebuild_ui": True,         # Rebuild frontend if ui/ changes
        "auto_apply": False,             # Safe release gate: notify only by default
        "last_checked": 0.0,
        "last_update_attempt": 0.0,
        "last_update_status": "idle",
        "last_update_log": ""
    }

    def get_auto_update_config(self) -> Dict[str, Any]:
        """
        Retrieves current Zero-Touch Auto-Update configuration (defaults to Enabled).
        Automatically creates and seeds database record for new and existing users.
        """
        cfg = self.get("system:auto_update_config")
        if not cfg or not isinstance(cfg, dict):
            # Seed default config into DB so it is permanently persisted for new & existing users
            cfg = dict(self.DEFAULT_AUTO_UPDATE_CONFIG)
            self.set("system:auto_update_config", cfg)
            return cfg
        merged = dict(self.DEFAULT_AUTO_UPDATE_CONFIG)
        merged.update(cfg)
        return merged

    def set_auto_update_config(self, config: Dict[str, Any]) -> bool:
        """Persists Auto-Update configuration and broadcasts mutation event."""
        current = self.get_auto_update_config()
        current.update(config)
        success = self.set("system:auto_update_config", current)
        event_bus.notify_mutation("AUTO_UPDATE_CONFIG", "system:auto_update_config", 0)
        return success

    def record_auto_update_event(
        self,
        status: str,
        from_commit: str = "",
        to_commit: str = "",
        from_version: str = "",
        to_version: str = "",
        ui_rebuilt: bool = False,
        log: str = ""
    ) -> int:
        """Records an entry in pg_auto_update_ledger."""
        conn = self._get_connection()
        now = time.time()
        cursor = conn.execute("""
            INSERT INTO pg_auto_update_ledger (
                triggered_at, status, from_commit, to_commit,
                from_version, to_version, ui_rebuilt, log, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            now, status, from_commit, to_commit,
            from_version, to_version, 1 if ui_rebuilt else 0, log, now
        ))
        conn.commit()
        return cursor.lastrowid

    def get_auto_update_logs(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Retrieves recent auto-update history."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT * FROM pg_auto_update_ledger
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        rows = cursor.fetchall()
        entries = []
        for r in rows:
            entries.append({
                "id": r["id"],
                "triggered_at": r["triggered_at"],
                "status": r["status"],
                "from_commit": r["from_commit"],
                "to_commit": r["to_commit"],
                "from_version": r["from_version"],
                "to_version": r["to_version"],
                "ui_rebuilt": bool(r["ui_rebuilt"]),
                "log": r["log"],
                "scope": r["scope"] if "scope" in r.keys() else "default",
                "context_hash": r["context_hash"] if "context_hash" in r.keys() else "",
                "expires_at": r["expires_at"] if "expires_at" in r.keys() else None,
                "created_at": r["created_at"],
                "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"]))
            })
        return entries

    def get_cached_response(self, cache_key: str, scope: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Retrieves cached response by cache_key and optional scope.
        Validates TTL expiration; deletes expired entry and returns None if expired.
        Atomically increments hit_count and tokens_saved_total.
        """
        conn = self._get_connection()
        now = time.time()

        if scope:
            cursor = conn.execute(
                "SELECT * FROM pg_semantic_cache WHERE cache_key = ? AND (scope = ? OR scope = 'default')",
                (cache_key, scope)
            )
        else:
            cursor = conn.execute("SELECT * FROM pg_semantic_cache WHERE cache_key = ?", (cache_key,))

        row = cursor.fetchone()
        if not row:
            return None

        # Check TTL expiration
        expires_at = row["expires_at"]
        if expires_at is not None and expires_at <= now:
            conn.execute("DELETE FROM pg_semantic_cache WHERE id = ?", (row["id"],))
            return None

        # Increment hit count and accumulate saved tokens
        conn.execute("""
            UPDATE pg_semantic_cache
            SET hit_count = hit_count + 1,
                tokens_saved_total = tokens_saved_total + total_tokens,
                last_hit_at = ?
            WHERE id = ?
        """, (now, row["id"]))

        return {
            "id": row["id"],
            "cache_key": row["cache_key"],
            "scope": row["scope"] if "scope" in row.keys() else "default",
            "context_hash": row["context_hash"] if "context_hash" in row.keys() else "",
            "prompt_hash": row["prompt_hash"],
            "prompt_preview": row["prompt_preview"],
            "response_text": row["response_text"],
            "model": row["model"],
            "prompt_tokens": row["prompt_tokens"],
            "completion_tokens": row["completion_tokens"],
            "reasoning_tokens": row["reasoning_tokens"],
            "total_tokens": row["total_tokens"],
            "hit_count": row["hit_count"] + 1,
            "tokens_saved_total": row["tokens_saved_total"] + row["total_tokens"],
            "created_at": row["created_at"],
            "expires_at": row["expires_at"] if "expires_at" in row.keys() else None,
            "last_hit_at": now
        }

    def store_cached_response(
        self,
        cache_key: str,
        prompt_hash: str,
        prompt_preview: str,
        response_text: str,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        reasoning_tokens: int = 0,
        embedding: Optional[bytes] = None,
        tools_signature: Optional[str] = None,
        scope: str = "default",
        context_hash: str = "",
        ttl_seconds: int = 86400,
        embedding_model: Optional[str] = None,
        embedding_dim: Optional[int] = None
    ) -> bool:
        """Stores a generated completion response in the persistent binary cache with TTL & LRU management."""
        try:
            total_tokens = prompt_tokens + completion_tokens + reasoning_tokens
            now = time.time()
            preview = (prompt_preview or "").strip()[:300]
            expires_at = (now + ttl_seconds) if ttl_seconds > 0 else None

            conn = self._get_connection()
            conn.execute("""
                INSERT INTO pg_semantic_cache (
                    cache_key, prompt_hash, prompt_preview, response_text,
                    model, prompt_tokens, completion_tokens, reasoning_tokens,
                    total_tokens, hit_count, tokens_saved_total, created_at, last_hit_at,
                    embedding, tools_signature, scope, context_hash, expires_at,
                    embedding_model, embedding_dim
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 0, 0, ?, NULL, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    response_text = excluded.response_text,
                    prompt_tokens = excluded.prompt_tokens,
                    completion_tokens = excluded.completion_tokens,
                    reasoning_tokens = excluded.reasoning_tokens,
                    total_tokens = excluded.total_tokens,
                    embedding = COALESCE(excluded.embedding, pg_semantic_cache.embedding),
                    tools_signature = COALESCE(excluded.tools_signature, pg_semantic_cache.tools_signature),
                    scope = excluded.scope,
                    context_hash = excluded.context_hash,
                    expires_at = excluded.expires_at,
                    embedding_model = COALESCE(excluded.embedding_model, pg_semantic_cache.embedding_model),
                    embedding_dim = COALESCE(excluded.embedding_dim, pg_semantic_cache.embedding_dim)
            """, (
                cache_key, prompt_hash, preview, response_text,
                model, prompt_tokens, completion_tokens, reasoning_tokens,
                total_tokens, now, embedding, tools_signature,
                scope, context_hash, expires_at, embedding_model, embedding_dim
            ))

            # Maintain capacity bounds
            cfg = self.get_cache_config()
            max_entries = cfg.get("max_entries", 5000)
            self.enforce_lru_capacity(max_entries)

            event_bus.notify_mutation("CACHE_STORE", cache_key, 0)
            return True
        except Exception as e:
            logger.error(f"Failed to store cached response for '{cache_key}': {e}")
            return False

    def find_semantic_match(
        self,
        model: str,
        query_vec: Any,
        scope: str = "default",
        context_hash: str = "",
        threshold: float = 0.93,
        tools_signature: Optional[str] = None
    ) -> Optional[Tuple[Dict[str, Any], float]]:
        """
        Scans cached entries strictly matching scope, context_hash, and model.
        Guarantees that differing context_hash will NEVER hit.
        Returns (matched_entry, similarity_score) if cosine score >= threshold.
        """
        if query_vec is None:
            return None

        from prime_gate.cache.semantic import SemanticVectorEngine

        conn = self._get_connection()
        now = time.time()
        sig_val = (tools_signature or "").strip()

        # Context-aware strict partition
        query_sql = """
            SELECT * FROM pg_semantic_cache
            WHERE (scope = ? OR scope = 'default')
              AND context_hash = ?
              AND model = ?
              AND embedding IS NOT NULL
              AND (expires_at IS NULL OR expires_at > ?)
        """
        params = [scope, context_hash, model, now]

        if sig_val:
            query_sql += " AND tools_signature = ?"
            params.append(sig_val)

        cursor = conn.execute(query_sql, params)
        rows = cursor.fetchall()
        if not rows:
            return None

        candidates = [dict(r) for r in rows]
        match = SemanticVectorEngine.find_best_semantic_match(query_vec, candidates, threshold=threshold)
        if not match:
            return None

        row, score = match
        # Atomically increment hit stats
        conn.execute("""
            UPDATE pg_semantic_cache
            SET hit_count = hit_count + 1,
                tokens_saved_total = tokens_saved_total + total_tokens,
                last_hit_at = ?
            WHERE id = ?
        """, (now, row["id"]))

        row["hit_count"] = row.get("hit_count", 0) + 1
        row["tokens_saved_total"] = row.get("tokens_saved_total", 0) + row.get("total_tokens", 0)
        row["last_hit_at"] = now
        return row, score

    def cleanup_expired_cache(self, ttl_seconds: Optional[int] = None) -> int:
        """Deletes cache entries that have passed their expiration timestamp."""
        conn = self._get_connection()
        now = time.time()
        deleted = 0
        if ttl_seconds is not None and ttl_seconds > 0:
            cutoff = now - ttl_seconds
            res = conn.execute("DELETE FROM pg_semantic_cache WHERE created_at < ?", (cutoff,))
            deleted += res.rowcount
        res2 = conn.execute("DELETE FROM pg_semantic_cache WHERE expires_at IS NOT NULL AND expires_at <= ?", (now,))
        deleted += res2.rowcount
        return deleted

    def enforce_lru_capacity(self, max_entries: int = 5000) -> int:
        """Removes least recently used cache entries when count exceeds max_entries."""
        conn = self._get_connection()
        count = conn.execute("SELECT COUNT(*) FROM pg_semantic_cache").fetchone()[0] or 0
        if count <= max_entries:
            return 0
        excess = count - max_entries
        conn.execute("""
            DELETE FROM pg_semantic_cache
            WHERE id IN (
                SELECT id FROM pg_semantic_cache
                ORDER BY COALESCE(last_hit_at, created_at) ASC
                LIMIT ?
            )
        """, (excess,))
        return excess

    def verify_or_rebuild_vector_index(self, active_model: str, active_dim: int) -> bool:
        """
        Checks if active embedding model or dimension has changed compared to indexed vectors.
        If changed, purges incompatible embedding BLOBs so they can be re-embedded cleanly.
        """
        meta = self.get("cache:vector_index_metadata")
        if meta and isinstance(meta, dict):
            stored_model = meta.get("model_name")
            stored_dim = meta.get("dimension")
            if stored_model != active_model or stored_dim != active_dim:
                logger.warning(
                    f"[VECTOR INDEX REBUILD] Detected model change from '{stored_model}' ({stored_dim}-dim) "
                    f"to '{active_model}' ({active_dim}-dim). Purging incompatible vector embeddings..."
                )
                conn = self._get_connection()
                conn.execute("UPDATE pg_semantic_cache SET embedding = NULL WHERE embedding_dim != ? OR (embedding_dim IS NULL AND embedding_model != ?);", (active_dim, active_model))
                self.set("cache:vector_index_metadata", {
                    "model_name": active_model,
                    "dimension": active_dim,
                    "updated_at": time.time()
                })
                return True
        else:
            self.set("cache:vector_index_metadata", {
                "model_name": active_model,
                "dimension": active_dim,
                "updated_at": time.time()
            })
        return False

    def record_cache_verification(
        self,
        cache_id: Optional[int],
        cache_type: str,
        similarity_score: float,
        upstream_similarity: float,
        is_false_hit: bool,
        details: str = ""
    ) -> bool:
        """Records a background verification sample to evaluate false-hit rate."""
        try:
            conn = self._get_connection()
            now = time.time()
            conn.execute("""
                INSERT INTO pg_cache_verifications (
                    cache_id, timestamp, cache_type, similarity_score,
                    upstream_similarity, is_false_hit, details
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (cache_id, now, cache_type, similarity_score, upstream_similarity, 1 if is_false_hit else 0, details))
            return True
        except Exception as e:
            logger.warning(f"Failed to record cache verification: {e}")
            return False

    def get_verification_stats(self) -> Dict[str, Any]:
        """Returns background verification statistics and estimated false-hit rate."""
        conn = self._get_connection()
        total = conn.execute("SELECT COUNT(*) FROM pg_cache_verifications").fetchone()[0] or 0
        false_hits = conn.execute("SELECT COUNT(*) FROM pg_cache_verifications WHERE is_false_hit = 1").fetchone()[0] or 0
        avg_upstream_sim = conn.execute("SELECT AVG(upstream_similarity) FROM pg_cache_verifications WHERE upstream_similarity IS NOT NULL").fetchone()[0] or 0.0
        false_hit_rate = round((false_hits / total * 100), 2) if total > 0 else 0.0
        return {
            "total_verifications": total,
            "false_hits": false_hits,
            "false_hit_rate_pct": false_hit_rate,
            "avg_upstream_similarity": round(float(avg_upstream_sim), 4)
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """Calculates global caching efficiency, total tokens saved, and hit ratio."""
        conn = self._get_connection()
        total_entries = conn.execute("SELECT COUNT(*) FROM pg_semantic_cache").fetchone()[0] or 0
        total_hits = conn.execute("SELECT SUM(hit_count) FROM pg_semantic_cache").fetchone()[0] or 0
        total_tokens_saved = conn.execute("SELECT SUM(tokens_saved_total) FROM pg_semantic_cache").fetchone()[0] or 0
        
        # Calculate from request logs
        log_hits = conn.execute("SELECT COUNT(*) FROM pg_request_logs WHERE cache_hit = 1").fetchone()[0] or 0
        log_total_reqs = conn.execute("SELECT COUNT(*) FROM pg_request_logs").fetchone()[0] or 0
        log_tokens_saved = conn.execute("SELECT SUM(tokens_saved) FROM pg_request_logs WHERE cache_hit = 1").fetchone()[0] or 0
        
        # Granular hit breakdowns
        exact_hits = conn.execute("SELECT COUNT(*) FROM pg_request_logs WHERE cache_hit = 1 AND cache_hit_type = 1").fetchone()[0] or 0
        semantic_hits = conn.execute("SELECT COUNT(*) FROM pg_request_logs WHERE cache_hit = 1 AND cache_hit_type = 2").fetchone()[0] or 0
        upstream_hits = conn.execute("SELECT COUNT(*) FROM pg_request_logs WHERE cache_hit = 1 AND cache_hit_type = 3").fetchone()[0] or 0

        final_tokens_saved = max(total_tokens_saved, log_tokens_saved)
        final_hits = max(total_hits, log_hits)
        hit_ratio = round((final_hits / log_total_reqs * 100), 1) if log_total_reqs > 0 else 0.0
        est_seconds_saved = round(final_hits * 2.5, 1)
        usd_saved = round((final_tokens_saved * 0.000005), 2)
        idr_saved = int(usd_saved * 16250)
        cfg = self.get_cache_config()

        v_stats = self.get_verification_stats()
        compactor_total_saved = int(self.get("telemetry:compactor_tokens_saved_total") or 0)
        return {
            "compactor_tokens_saved_total": compactor_total_saved,
            "total_entries": total_entries,
            "verification_stats": v_stats,
            "total_hits": final_hits,
            "exact_hits": exact_hits,
            "semantic_hits": semantic_hits,
            "upstream_hits": upstream_hits,
            "total_tokens_saved": final_tokens_saved,
            "hit_ratio_pct": hit_ratio,
            "estimated_seconds_saved": est_seconds_saved,
            "usd_value_saved": usd_saved,
            "idr_value_saved": idr_saved,
            "config": cfg
        }

    def list_cache_entries(
        self,
        limit: int = 50,
        offset: int = 0,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """Retrieves paginated list of active cache items."""
        conn = self._get_connection()
        query = "SELECT * FROM pg_semantic_cache WHERE 1=1"
        params = []

        if search:
            query += " AND (prompt_preview LIKE ? OR model LIKE ? OR cache_key LIKE ?)"
            term = f"%{search}%"
            params.extend([term, term, term])

        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total_count = conn.execute(count_query, params).fetchone()[0]

        query += " ORDER BY hit_count DESC, created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()

        entries = []
        for r in rows:
            entries.append({
                "id": r["id"],
                "cache_key": r["cache_key"],
                "prompt_preview": r["prompt_preview"],
                "response_preview": (r["response_text"] or "")[:200],
                "response_text": r["response_text"] or "",
                "model": r["model"],
                "total_tokens": r["total_tokens"],
                "prompt_tokens": r["prompt_tokens"],
                "completion_tokens": r["completion_tokens"],
                "hit_count": r["hit_count"],
                "tokens_saved_total": r["tokens_saved_total"],
                "scope": r["scope"] if "scope" in r.keys() else "default",
                "context_hash": r["context_hash"] if "context_hash" in r.keys() else "",
                "expires_at": r["expires_at"] if "expires_at" in r.keys() else None,
                "created_at": r["created_at"],
                "created_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["created_at"])),
                "last_hit_formatted": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["last_hit_at"])) if r["last_hit_at"] else "Never"
            })

        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "entries": entries
        }

    def clear_cache(self) -> bool:
        """Flushes all entries from pg_semantic_cache."""
        try:
            conn = self._get_connection()
            conn.execute("DELETE FROM pg_semantic_cache;")
            event_bus.notify_mutation("CACHE_CLEAR", "all", 0)
            return True
        except Exception as e:
            logger.error(f"Failed to clear cache: {e}")
            return False

    def delete_cache_entry(self, entry_id: int) -> bool:
        """Deletes a specific cache entry by ID."""
        try:
            conn = self._get_connection()
            conn.execute("DELETE FROM pg_semantic_cache WHERE id = ?;", (entry_id,))
            event_bus.notify_mutation("CACHE_DELETE", str(entry_id), 0)
            return True
        except Exception as e:
            logger.error(f"Failed to delete cache entry {entry_id}: {e}")
            return False

    def clear_request_logs(self) -> bool:
        """Clears all request logs from the database."""
        try:
            conn = self._get_connection()
            conn.execute("DELETE FROM pg_request_logs;")
            return True
        except Exception as e:
            logger.error(f"Failed to clear request logs: {e}")
            return False

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None


    def create_backup(self, label: str = "") -> Path:
        """Creates a timestamped backup copy of the database using atomic SQLite backup API."""
        backup_dir = self.db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        label_part = f"_{label}" if label else ""
        backup_file = backup_dir / f"prime_gate_{timestamp}{label_part}.pgdb"

        dest_conn = sqlite3.connect(str(backup_file))
        try:
            self._get_connection().backup(dest_conn)
        finally:
            dest_conn.close()

        logger.info(f"Database backup created: {backup_file}")
        return backup_file

    def rollback_from_backup(self, backup_file: Path) -> bool:
        """Restores active database from a backup file using atomic SQLite backup API."""
        target = Path(backup_file)
        if not target.exists():
            logger.error(f"Cannot rollback: Backup file '{target}' does not exist.")
            return False

        src_conn = sqlite3.connect(str(target))
        try:
            src_conn.backup(self._get_connection())
        except Exception as e:
            logger.error(f"SQLite rollback backup API failed: {e}")
            return False
        finally:
            src_conn.close()

        logger.warning(f"Database rolled back successfully from: {target}")
        return True

    def rollback_latest_backup(self) -> Tuple[bool, str]:
        """Finds the most recent backup in data/backups/ and restores it."""
        backup_dir = self.db_path.parent / "backups"
        if not backup_dir.exists():
            return False, "No backups directory found"
        backups = sorted(backup_dir.glob("*.pgdb"), key=os.path.getmtime, reverse=True)
        if not backups:
            return False, "No backup files found"
        latest = backups[0]
        success = self.rollback_from_backup(latest)
        return success, str(latest)

    def migrate_v1_to_v2(self) -> int:
        """
        Idempotent automatic migration from legacy V1 (XOR) to V2 (AES-256-GCM).
        Creates an encrypted/safe backup prior to migration.
        Returns count of migrated records.
        """
        conn = self._get_connection()
        cursor = conn.execute("SELECT key, record_type, data FROM pg_records")
        rows = cursor.fetchall()
        v1_records = []
        for r in rows:
            data = r["data"]
            if len(data) >= 6:
                magic, version = struct.unpack(">4sH", data[:6])
                if magic == b"PGDB" and version == 1:
                    v1_records.append(r)

        if not v1_records:
            return 0

        logger.info(f"Found {len(v1_records)} legacy V1 record(s). Creating backup before AES-256-GCM migration...")
        backup_path = self.create_backup("pre_v2_migration")
        migrated_count = 0
        try:
            for r in v1_records:
                key = r["key"]
                rec_type = r["record_type"]
                _, payload, ts = BinaryCodec.unpack(r["data"], key_name=key)
                new_blob = BinaryCodec.pack(rec_type, payload, key_name=key)
                _, _, _, _, stored_crc, _ = BinaryCodec.extract_header(new_blob)
                now = time.time()
                conn.execute(
                    "UPDATE pg_records SET data = ?, crc32 = ?, updated_at = ? WHERE key = ?",
                    (new_blob, stored_crc, now, key)
                )
                migrated_count += 1
            logger.info(f"Successfully migrated {migrated_count} record(s) to AES-256-GCM at rest.")
            return migrated_count
        except Exception as e:
            logger.critical(f"Database V2 migration failed: {e}. Initiating automatic rollback from {backup_path}...")
            self.rollback_from_backup(backup_path)
            raise RuntimeError(f"Database migration aborted and rolled back: {e}")

    def rotate_database_key(self, new_key: Optional[bytes] = None) -> bool:
        """
        Re-encrypts all database records with a new master key.
        Creates a backup first.
        """
        backup_path = self.create_backup("pre_key_rotation")
        try:
            conn = self._get_connection()
            cursor = conn.execute("SELECT key, record_type, data FROM pg_records")
            rows = cursor.fetchall()

            decrypted = []
            for r in rows:
                key = r["key"]
                rec_type = r["record_type"]
                _, payload, _ = BinaryCodec.unpack(r["data"], key_name=key)
                decrypted.append((key, rec_type, payload))

            rotated_key = KeyManager.rotate_master_key(new_key)

            for key, rec_type, payload in decrypted:
                new_blob = BinaryCodec.pack(rec_type, payload, key_name=key, key=rotated_key)
                _, _, _, _, stored_crc, _ = BinaryCodec.extract_header(new_blob)
                now = time.time()
                conn.execute(
                    "UPDATE pg_records SET data = ?, crc32 = ?, updated_at = ? WHERE key = ?",
                    (new_blob, stored_crc, now, key)
                )
            logger.info(f"Database successfully re-encrypted {len(decrypted)} record(s) with rotated master key.")
            return True
        except Exception as e:
            logger.critical(f"Master key rotation failed: {e}. Rolling back...")
            self.rollback_from_backup(backup_path)
            raise RuntimeError(f"Key rotation failed and database was restored: {e}")

    def create_api_key(
        self,
        name: str = "default",
        rate_limit_rpm: int = 0,
        rate_limit_tpd: int = 0,
        quota_credits: float = 0.0,
        allowed_models: Any = "[]",
        cache_scope: str = "shared"
    ) -> Tuple[str, Dict[str, Any]]:
        """Generates a new Client Gateway API key, stores SHA-256+salt hash and policies in DB, and returns (raw_key, record)."""
        raw_key, record = AuthManager.generate_api_key(name)
        if isinstance(allowed_models, (list, set, tuple)):
            allowed_models_str = json.dumps(list(allowed_models))
        elif isinstance(allowed_models, str):
            allowed_models_str = allowed_models
        else:
            allowed_models_str = "[]"

        cache_scope_clean = str(cache_scope).lower().strip()
        if cache_scope_clean not in ("shared", "key", "disabled"):
            cache_scope_clean = "shared"

        conn = self._get_connection()
        cursor = conn.execute("""
            INSERT INTO pg_api_keys (
                name, prefix, key_hash, salt, created_at,
                rate_limit_rpm, rate_limit_tpd, quota_credits, allowed_models, cache_scope
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            record["name"], record["prefix"], record["key_hash"], record["salt"], record["created_at"],
            int(rate_limit_rpm or 0), int(rate_limit_tpd or 0), float(quota_credits or 0.0),
            allowed_models_str, cache_scope_clean
        ))
        record["id"] = cursor.lastrowid
        record["rate_limit_rpm"] = int(rate_limit_rpm or 0)
        record["rate_limit_tpd"] = int(rate_limit_tpd or 0)
        record["quota_credits"] = float(quota_credits or 0.0)
        record["allowed_models"] = allowed_models_str
        record["cache_scope"] = cache_scope_clean
        return raw_key, record

    def list_api_keys(self) -> List[Dict[str, Any]]:
        """Lists all Client Gateway API keys with sanitized fields (never outputs salt or key_hash)."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT id, name, prefix, created_at, last_used_at, revoked_at,
                   rate_limit_rpm, rate_limit_tpd, quota_credits, allowed_models, cache_scope
            FROM pg_api_keys
            ORDER BY id ASC
        """)
        return [dict(r) for r in cursor.fetchall()]

    def get_active_api_keys(self) -> List[Dict[str, Any]]:
        """Returns all unrevoked Client Gateway API keys including hash for internal verification."""
        conn = self._get_connection()
        cursor = conn.execute("""
            SELECT id, name, prefix, key_hash, salt, created_at, last_used_at, revoked_at,
                   rate_limit_rpm, rate_limit_tpd, quota_credits, allowed_models, cache_scope
            FROM pg_api_keys
            WHERE revoked_at IS NULL
        """)
        return [dict(r) for r in cursor.fetchall()]

    def record_api_key_tokens(self, key_id: int, prompt_tokens: int, completion_tokens: int, model: str):
        """Records token usage for a Client Gateway API key in pg_api_key_usage."""
        try:
            total = int(prompt_tokens or 0) + int(completion_tokens or 0)
            conn = self._get_connection()
            conn.execute("""
                INSERT INTO pg_api_key_usage (key_id, prompt_tokens, completion_tokens, total_tokens, model, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (int(key_id), int(prompt_tokens or 0), int(completion_tokens or 0), total, str(model or ""), time.time()))
        except Exception as e:
            logger.warning(f"Failed to record API key usage for key {key_id}: {e}")

    def get_api_key_usage_today(self, key_id: int) -> int:
        """Returns total LLM tokens used by key_id in the last 24 hours."""
        try:
            cutoff = time.time() - 86400.0
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT SUM(total_tokens) as total
                FROM pg_api_key_usage
                WHERE key_id = ? AND created_at >= ?
            """, (int(key_id), cutoff))
            row = cursor.fetchone()
            if row and row["total"] is not None:
                return int(row["total"])
            return 0
        except Exception:
            return 0

    def get_api_key_lifetime_usage(self, key_id: int) -> int:
        """Returns cumulative lifetime LLM tokens used by key_id."""
        try:
            conn = self._get_connection()
            cursor = conn.execute("""
                SELECT SUM(total_tokens) as total
                FROM pg_api_key_usage
                WHERE key_id = ?
            """, (int(key_id),))
            row = cursor.fetchone()
            if row and row["total"] is not None:
                return int(row["total"])
            return 0
        except Exception:
            return 0

    def revoke_api_key(self, key_id_or_name: str) -> bool:
        """Revokes an API key by numeric ID or name."""
        conn = self._get_connection()
        now = time.time()
        cursor = conn.execute("""
            UPDATE pg_api_keys
            SET revoked_at = ?
            WHERE (CAST(id AS TEXT) = ? OR name = ?) AND revoked_at IS NULL
        """, (now, str(key_id_or_name), str(key_id_or_name)))
        return cursor.rowcount > 0

    def update_api_key_last_used(self, key_id: int):
        conn = self._get_connection()
        conn.execute("UPDATE pg_api_keys SET last_used_at = ? WHERE id = ?", (time.time(), key_id))

    def ensure_default_api_key(self) -> Optional[str]:
        """Creates a default API key if the table is empty and returns the raw key."""
        conn = self._get_connection()
        cursor = conn.execute("SELECT COUNT(*) as cnt FROM pg_api_keys")
        row = cursor.fetchone()
        if row and row["cnt"] == 0:
            raw_key, record = self.create_api_key("default")
            logger.info("Generated initial default API Key.")
            return raw_key
        return None


# Global Singleton Database Engine
db = BinaryDatabaseEngine()

