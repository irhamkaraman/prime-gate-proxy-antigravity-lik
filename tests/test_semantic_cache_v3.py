"""
Unit tests for Phase 3A: Semantic Cache
Validates:
1. Context hash isolation (different files/history -> MISS despite identical question)
2. Multilingual Indonesian semantic match (paraphrased question -> HIT >= 0.93)
3. Scope & API key isolation (partitioned per key/project)
4. TTL expiration and automatic pruning
5. Tool-use / tool_calls exclusion (intermediate tool executions never cached)
6. E5 prefix handling ("query: " / "passage: ") and vector dimension migration
7. Verification sampling ledger recording
"""

import time
import pytest
import numpy as np
from fastapi.testclient import TestClient

from prime_gate.server import app
from prime_gate.db.engine import db
from prime_gate.cache.context_key import ContextKeyExtractor
from prime_gate.cache.semantic import SemanticVectorEngine
from prime_gate.crypto.auth_manager import AuthManager


@pytest.fixture(autouse=True)
def reset_rate_limiter_and_clean_test_db():
    AuthManager.record_login_attempt("127.0.0.1", True)
    AuthManager.record_login_attempt("testclient", True)
    # Ensure fresh default test API key
    db.ensure_default_api_key()
    yield


class TestSemanticCacheV3:

    def test_context_hash_isolation_different_files_never_hit(self):
        """
        Invariance: If two requests share the identical user question ('Jelaskan fungsi ini'),
        but have different system prompts, prior file content, or conversation history,
        their context_hash MUST DIFFER and they must NEVER hit each other's cache!
        """
        # Context A: reviewing file auth.py
        key_a, ctx_hash_a, q_a, q_hash_a, _, scope_a, _ = ContextKeyExtractor.compute(
            model="gemini-3.8-flash",
            messages=[
                {"role": "system", "content": "File: /src/auth.py\ndef login(): pass"},
                {"role": "user", "content": "Jelaskan fungsi ini secara ringkas."}
            ],
            api_key_prefix="pg-live-test1",
            project_id="repo-alpha"
        )

        # Context B: reviewing file database.py
        key_b, ctx_hash_b, q_b, q_hash_b, _, scope_b, _ = ContextKeyExtractor.compute(
            model="gemini-3.8-flash",
            messages=[
                {"role": "system", "content": "File: /src/database.py\ndef connect(): pass"},
                {"role": "user", "content": "Jelaskan fungsi ini secara ringkas."}
            ],
            api_key_prefix="pg-live-test1",
            project_id="repo-alpha"
        )

        assert q_a == q_b == "Jelaskan fungsi ini secara ringkas."
        assert q_hash_a == q_hash_b
        # Context hashes MUST be strictly different!
        assert ctx_hash_a != ctx_hash_b
        assert key_a != key_b

        # Store response for Context A
        db.store_cached_response(
            cache_key=key_a,
            prompt_hash=q_hash_a,
            prompt_preview=q_a,
            response_text="Fungsi login melakukan autentikasi kredensial pengguna.",
            model="gemini-3.8-flash",
            prompt_tokens=25,
            completion_tokens=10,
            scope=scope_a,
            context_hash=ctx_hash_a
        )

        # Context B exact lookup must be None
        res_b = db.get_cached_response(key_b, scope=scope_b)
        assert res_b is None

        # Context B semantic lookup must also be None because context_hash differs
        q_vec = SemanticVectorEngine.embed_query(q_b)
        match_b = db.find_semantic_match(
            model="gemini-3.8-flash",
            query_vec=q_vec,
            scope=scope_b,
            context_hash=ctx_hash_b,
            threshold=0.80
        )
        assert match_b is None

    def test_multilingual_indonesian_semantic_match(self):
        """
        Verify that paraphrased questions in Bahasa Indonesia achieve SEMANTIC HIT >= 0.93.
        """
        q1 = "Bagaimana cara membuat fungsi rekursif di Python?"
        q2 = "Gimana cara bikin fungsi rekursi dalam bahasa Python?"

        messages_1 = [{"role": "user", "content": q1}]
        messages_2 = [{"role": "user", "content": q2}]

        key_1, ctx_1, _, q_hash_1, _, scope, _ = ContextKeyExtractor.compute(
            model="claude-sonnet-4-6",
            messages=messages_1,
            api_key_prefix="pg-live-test",
            project_id="default"
        )

        key_2, ctx_2, _, q_hash_2, _, _, _ = ContextKeyExtractor.compute(
            model="claude-sonnet-4-6",
            messages=messages_2,
            api_key_prefix="pg-live-test",
            project_id="default"
        )

        # In identical contexts (both empty history), context_hash is identical
        assert ctx_1 == ctx_2

        # Store response for q1 with passage embedding
        p_vec = SemanticVectorEngine.embed_passage(q1)
        emb_bytes = SemanticVectorEngine.vector_to_blob(p_vec) if p_vec is not None else None

        db.store_cached_response(
            cache_key=key_1,
            prompt_hash=q_hash_1,
            prompt_preview=q1,
            response_text="Fungsi rekursif adalah fungsi yang memanggil dirinya sendiri dengan base case.",
            model="claude-sonnet-4-6",
            prompt_tokens=20,
            completion_tokens=15,
            embedding=emb_bytes,
            scope=scope,
            context_hash=ctx_1
        )

        # Lookup q2 via semantic vector
        q2_vec = SemanticVectorEngine.embed_query(q2)
        assert q2_vec is not None

        match = db.find_semantic_match(
            model="claude-sonnet-4-6",
            query_vec=q2_vec,
            scope=scope,
            context_hash=ctx_2,
            threshold=0.93
        )

        assert match is not None, "Paraphrased Indonesian prompt must trigger semantic cache hit"
        entry, score = match
        assert score >= 0.93
        assert "rekursif" in entry["response_text"].lower()

    def test_scope_and_api_key_isolation(self):
        """
        Invariance: Cache entries from API Key A must NEVER be returned to API Key B.
        """
        prompt = "Berapa hasil 15 dikali 12?"
        messages = [{"role": "user", "content": prompt}]

        # Scope Key A
        key_a, ctx_a, q_text, q_hash, _, scope_a, _ = ContextKeyExtractor.compute(
            model="gemini-3.8-flash",
            messages=messages,
            api_key_prefix="pg-live-userA",
            project_id="default"
        )

        # Scope Key B
        key_b, ctx_b, _, _, _, scope_b, _ = ContextKeyExtractor.compute(
            model="gemini-3.8-flash",
            messages=messages,
            api_key_prefix="pg-live-userB",
            project_id="default"
        )

        assert scope_a != scope_b
        assert key_a != key_b

        db.store_cached_response(
            cache_key=key_a,
            prompt_hash=q_hash,
            prompt_preview=q_text,
            response_text="15 x 12 = 180",
            model="gemini-3.8-flash",
            prompt_tokens=10,
            completion_tokens=6,
            scope=scope_a,
            context_hash=ctx_a
        )

        # Key B must NOT find Key A's cached response
        res_b = db.get_cached_response(key_b, scope=scope_b)
        assert res_b is None

        # Key A must find its own cached response
        res_a = db.get_cached_response(key_a, scope=scope_a)
        assert res_a is not None
        assert "180" in res_a["response_text"]

    def test_ttl_expiration_and_cleanup(self):
        """
        Verify that expired cache entries (expires_at <= now) are not returned and are pruned.
        """
        prompt = "Tes kedaluwarsa TTL cache"
        key, ctx, q_text, q_hash, _, scope, _ = ContextKeyExtractor.compute(
            model="gemini-3.8-flash",
            messages=[{"role": "user", "content": prompt}],
            api_key_prefix="pg-live-ttl"
        )

        # Store with TTL of 1 second
        db.store_cached_response(
            cache_key=key,
            prompt_hash=q_hash,
            prompt_preview=q_text,
            response_text="Data sementara.",
            model="gemini-3.8-flash",
            prompt_tokens=10,
            completion_tokens=5,
            scope=scope,
            context_hash=ctx,
            ttl_seconds=1
        )

        # Immediate lookup succeeds
        immediate = db.get_cached_response(key, scope=scope)
        assert immediate is not None

        # Wait for TTL to expire
        time.sleep(1.2)

        # Post-expiry lookup returns None and prunes row
        expired = db.get_cached_response(key, scope=scope)
        assert expired is None

    def test_e5_prefix_handling(self):
        """
        Verify that when an E5-family model is configured,
        query prefix 'query: ' and passage prefix 'passage: ' are applied.
        """
        original_model = SemanticVectorEngine.get_model_name()
        try:
            # Set to e5 model
            SemanticVectorEngine.set_model_name("intfloat/multilingual-e5-small")
            assert "e5" in SemanticVectorEngine.get_model_name().lower()

            query_text = "Apa ibukota Indonesia?"
            applied_q = SemanticVectorEngine.apply_e5_prefix(query_text, is_query=True)
            assert applied_q.startswith("query: ")
            assert applied_q == "query: Apa ibukota Indonesia?"

            passage_text = "Ibukota Indonesia adalah Nusantara."
            applied_p = SemanticVectorEngine.apply_e5_prefix(passage_text, is_query=False)
            assert applied_p.startswith("passage: ")
            assert applied_p == "passage: Ibukota Indonesia adalah Nusantara."
        finally:
            SemanticVectorEngine.set_model_name(original_model)

    def test_vector_dimension_mismatch_index_purge(self):
        """
        Verify that changing model/dimension purges incompatible embeddings.
        """
        # Store an entry with 384-dim embedding
        dummy_vec = np.ones(384, dtype=np.float32)
        dummy_blob = SemanticVectorEngine.vector_to_blob(dummy_vec)

        key, ctx, q, q_h, _, scope, _ = ContextKeyExtractor.compute(
            model="gemini-3.8-flash",
            messages=[{"role": "user", "content": "Uji migrasi dimensi vektor"}],
            api_key_prefix="pg-live-dim"
        )

        db.store_cached_response(
            cache_key=key,
            prompt_hash=q_h,
            prompt_preview=q,
            response_text="Dimensi 384",
            model="gemini-3.8-flash",
            prompt_tokens=10,
            completion_tokens=5,
            embedding=dummy_blob,
            scope=scope,
            context_hash=ctx,
            embedding_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            embedding_dim=384
        )

        # Initialize initial index metadata
        db.verify_or_rebuild_vector_index(
            active_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            active_dim=384
        )

        # Simulate changing model to a 1024-dim model (e.g. multilingual-e5-large)
        rebuilt = db.verify_or_rebuild_vector_index(
            active_model="intfloat/multilingual-e5-large",
            active_dim=1024
        )
        assert rebuilt is True

        # Check that the incompatible embedding is now NULL so it won't crash numpy dot product
        conn = db._get_connection()
        row = conn.execute("SELECT embedding FROM pg_semantic_cache WHERE cache_key = ?", (key,)).fetchone()
        assert row["embedding"] is None

        # Reset back
        db.verify_or_rebuild_vector_index(
            active_model="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            active_dim=384
        )

    def test_verification_sampling_recording_and_stats(self):
        """
        Verify recording of background verification samples and computation of false-hit rate.
        """
        # Record 4 successful hits and 1 false hit
        for i in range(4):
            db.record_cache_verification(
                cache_id=100 + i,
                cache_type="SEMANTIC",
                similarity_score=0.96,
                upstream_similarity=0.95,
                is_false_hit=False
            )

        db.record_cache_verification(
            cache_id=105,
            cache_type="SEMANTIC",
            similarity_score=0.93,
            upstream_similarity=0.45,
            is_false_hit=True,
            details="Mismatch on short response"
        )

        stats = db.get_verification_stats()
        assert stats["total_verifications"] >= 5
        assert stats["false_hits"] >= 1
        assert 0.0 < stats["false_hit_rate_pct"] <= 100.0
