import json
import base64
from pathlib import Path
from prime_gate.db.engine import BinaryDatabaseEngine
from prime_gate.translator.thought_cache import (
    ThoughtSignatureCache,
    sanitize_thought_signature,
    DEFAULT_SKIP_SIGNATURE,
    is_valid_base64
)
from prime_gate.translator.request_converter import transform_openai_to_antigravity
from prime_gate.translator.anthropic_converter import transform_anthropic_to_antigravity


class TestThoughtSignaturePersistence:
    """
    Test suite for Two-Tier Persistent Thought Signature Cache and Request Adapters.
    Ensures 100% resilience against Gemini 3 'missing thought_signature in functionCall parts'
    and 'Base64 decoding failed' errors.
    """

    def test_sanitize_thought_signature(self):
        """Verifies sanitization rules: valid base64 preserved, malformed converted to skip validator."""
        # 1. Valid cryptographic Base64 string
        valid_b64 = base64.b64encode(b"real_crypto_token_content").decode("ascii")
        assert is_valid_base64(valid_b64) is True
        assert sanitize_thought_signature(valid_b64) == valid_b64

        # 2. Official Google bypass strings
        assert sanitize_thought_signature("skip_thought_signature_validator") == "skip_thought_signature_validator"
        assert sanitize_thought_signature("context_engineering_is_the_way_to_go") == "context_engineering_is_the_way_to_go"

        # 3. None / Empty
        assert sanitize_thought_signature(None) == DEFAULT_SKIP_SIGNATURE
        assert sanitize_thought_signature("") == DEFAULT_SKIP_SIGNATURE

        # 4. Malformed string with underscores (the exact error from user log)
        malformed = "ANTHROPIC_CRYPTO_TOKEN_TEST=="
        assert is_valid_base64(malformed) is False
        assert sanitize_thought_signature(malformed) == DEFAULT_SKIP_SIGNATURE

    def test_isolated_db_thought_signature_crud(self, tmp_path: Path):
        """Verifies SQLite WAL table stores and retrieves signatures accurately in an isolated DB."""
        test_db = BinaryDatabaseEngine(tmp_path / "isolated.pgdb")
        test_key = "test_call_101"
        test_sig = base64.b64encode(b"valid_signature_101").decode("ascii")
        test_fn = "default_api:read"
        test_args = {"path": "README.md"}
        call_hash = ThoughtSignatureCache.compute_call_hash(test_fn, test_args)

        stored = test_db.store_thought_signature(
            key=test_key,
            signature=test_sig,
            fn_name=test_fn,
            call_hash=call_hash,
            model="gemini-3.8-flash-high",
            ttl_seconds=3600
        )
        assert stored is True

        # Test retrieval by key
        assert test_db.get_thought_signature(test_key) == test_sig

        # Test retrieval by call hash
        assert test_db.get_thought_signature_by_hash(call_hash) == test_sig

        # Test invalid base64 is rejected from DB storage
        assert test_db.store_thought_signature(
            key="bad_key",
            signature="NOT_BASE_64_==__",
            fn_name="bash",
            call_hash="h123"
        ) is False

    def test_daemon_restart_survival(self, tmp_path: Path):
        """
        Simulates daemon kill and restart using an isolated SQLite database.
        Verifies that a brand new ThoughtSignatureCache instance restores tokens from SQLite.
        """
        isolated_db = BinaryDatabaseEngine(tmp_path / "restart_test.pgdb")
        call_id = "call_restart_survivor_999"
        sig_data = base64.b64encode(b"restart_token_data").decode("ascii")
        fn_name = "default_api:grep"
        fn_args = {"query": "thought_signature"}
        chash = ThoughtSignatureCache.compute_call_hash(fn_name, fn_args)

        # Store directly in DB
        isolated_db.store_thought_signature(
            key=call_id,
            signature=sig_data,
            fn_name=fn_name,
            call_hash=chash,
            model="gemini-3.8-flash-high"
        )
        isolated_db.store_thought_signature(
            key=f"hash:{chash}",
            signature=sig_data,
            fn_name=fn_name,
            call_hash=chash,
            model="gemini-3.8-flash-high"
        )

        # Create fresh cache instance
        cache2 = ThoughtSignatureCache(ttl_seconds=3600)
        assert call_id not in cache2._cache

        # Mock db reference for cache2
        from unittest.mock import patch
        with patch("prime_gate.db.db", isolated_db):
            recovered = cache2.get(call_id)
            assert recovered == sig_data

            # Hash lookup must also recover
            assert cache2.get_by_hash(chash) == sig_data

            # Resolver must resolve exact match
            assert cache2.resolve_signature(call_id=call_id, fn_name=fn_name, fn_args=fn_args) == sig_data

            # Unknown call must safely fall back to skip validator
            assert cache2.resolve_signature(call_id="unknown_123", fn_name="unknown_tool") == DEFAULT_SKIP_SIGNATURE

    def test_openai_translator_restores_or_bypasses_signature(self):
        """
        Verifies transform_openai_to_antigravity restores cached thoughtSignature,
        and uses official Google bypass signature when receiving bare tool_calls.
        """
        test_call_id = "call_opencode_bare_turn_5"
        test_sig = base64.b64encode(b"valid_cached_signature").decode("ascii")
        fn_name = "default_api:read"
        fn_args = {"path": ".config/opencode/opencode.json"}

        # Seed in-memory cache directly
        from prime_gate.translator.thought_cache import thought_sig_cache
        thought_sig_cache._cache[test_call_id] = (test_sig, 9999999999.0)

        # Case 1: Call is in cache -> restored
        client_body = {
            "model": "antigravity-gemini-3.8-flash-high",
            "messages": [
                {"role": "user", "content": "Read my config file"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": test_call_id,
                            "type": "function",
                            "function": {
                                "name": fn_name,
                                "arguments": json.dumps(fn_args)
                            }
                        }
                    ]
                },
                {
                    "role": "tool",
                    "tool_call_id": test_call_id,
                    "name": fn_name,
                    "content": '{"status": "ok", "lines": 40}'
                },
                {"role": "user", "content": "tolong tambahkan search juga"}
            ]
        }

        model, payload = transform_openai_to_antigravity(client_body)
        contents = payload.get("contents", [])
        model_turn = [c for c in contents if c.get("role") == "model"][0]
        fc_part = [p for p in model_turn["parts"] if "functionCall" in p][0]

        assert fc_part["functionCall"]["name"] == fn_name
        assert fc_part["thoughtSignature"] == test_sig

        # Case 2: Brand new uncached bare tool call -> automatically uses official Google bypass
        uncached_body = {
            "model": "antigravity-gemini-3.8-flash-high",
            "messages": [
                {"role": "user", "content": "Search things"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "uncached_call_999",
                            "type": "function",
                            "function": {
                                "name": "default_api:search",
                                "arguments": '{"query": "antigravity"}'
                            }
                        }
                    ]
                },
                {
                    "role": "tool",
                    "tool_call_id": "uncached_call_999",
                    "name": "default_api:search",
                    "content": '{"found": 5}'
                },
                {"role": "user", "content": "Proceed"}
            ]
        }
        _, uncached_payload = transform_openai_to_antigravity(uncached_body)
        uncached_model_turn = [c for c in uncached_payload["contents"] if c.get("role") == "model"][0]
        uncached_fc = [p for p in uncached_model_turn["parts"] if "functionCall" in p][0]
        assert uncached_fc["thoughtSignature"] == DEFAULT_SKIP_SIGNATURE

        # Clean up test cache
        thought_sig_cache._cache.pop(test_call_id, None)

    def test_anthropic_translator_restores_or_bypasses_signature(self):
        """
        Verifies transform_anthropic_to_antigravity restores cached thoughtSignature,
        and uses official Google bypass signature when receiving bare Anthropic tool_use blocks.
        """
        test_call_id = "toolu_anthropic_abc_123"
        test_sig = base64.b64encode(b"valid_anthropic_sig").decode("ascii")
        fn_name = "default_api:search"
        fn_args = {"query": "antigravity"}

        from prime_gate.translator.thought_cache import thought_sig_cache
        thought_sig_cache._cache[test_call_id] = (test_sig, 9999999999.0)

        # Case 1: In cache
        anthropic_body = {
            "model": "claude-3-7-sonnet",
            "messages": [
                {"role": "user", "content": "Search codebase"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": test_call_id,
                            "name": fn_name,
                            "input": fn_args
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": test_call_id,
                            "content": "found 3 files"
                        }
                    ]
                }
            ]
        }

        model, payload = transform_anthropic_to_antigravity(anthropic_body)
        contents = payload.get("contents", [])
        model_turn = [c for c in contents if c.get("role") == "model"][0]
        fc_part = [p for p in model_turn["parts"] if "functionCall" in p][0]

        assert fc_part["functionCall"]["name"] == fn_name
        assert fc_part["thoughtSignature"] == test_sig

        # Case 2: Uncached bare tool_use block
        uncached_anthropic = {
            "model": "claude-3-7-sonnet",
            "messages": [
                {"role": "user", "content": "Execute"},
                {
                    "role": "assistant",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "toolu_bare_999",
                            "name": "bash",
                            "input": {"command": "ls"}
                        }
                    ]
                },
                {
                    "role": "user",
                    "content": [{"type": "tool_result", "tool_use_id": "toolu_bare_999", "content": "ok"}]
                }
            ]
        }
        _, uncached_payload = transform_anthropic_to_antigravity(uncached_anthropic)
        uncached_model = [c for c in uncached_payload["contents"] if c.get("role") == "model"][0]
        uncached_fc = [p for p in uncached_model["parts"] if "functionCall" in p][0]
        assert uncached_fc["thoughtSignature"] == DEFAULT_SKIP_SIGNATURE

        # Clean up test cache
        thought_sig_cache._cache.pop(test_call_id, None)
