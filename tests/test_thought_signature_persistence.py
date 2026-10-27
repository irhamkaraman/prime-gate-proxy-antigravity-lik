import json
from prime_gate.db import db
from prime_gate.translator.thought_cache import ThoughtSignatureCache
from prime_gate.translator.request_converter import transform_openai_to_antigravity
from prime_gate.translator.anthropic_converter import transform_anthropic_to_antigravity


class TestThoughtSignaturePersistence:
    """
    Test suite for Two-Tier Persistent Thought Signature Cache and Request Adapters.
    Ensures 100% resilience against Gemini 3 'missing thought_signature in functionCall parts' errors.
    """

    def test_db_thought_signature_crud(self):
        """Verifies SQLite WAL table stores and retrieves signatures accurately."""
        test_key = "test_call_101"
        test_sig = "RVg4QV9URVNUX0NSWVBUT19TSUdOQVRVUkU="
        test_fn = "default_api:read"
        test_args = {"path": "README.md"}
        call_hash = ThoughtSignatureCache.compute_call_hash(test_fn, test_args)

        stored = db.store_thought_signature(
            key=test_key,
            signature=test_sig,
            fn_name=test_fn,
            call_hash=call_hash,
            model="gemini-3.8-flash-high",
            ttl_seconds=3600
        )
        assert stored is True

        # Test retrieval by key
        assert db.get_thought_signature(test_key) == test_sig

        # Test retrieval by call hash
        assert db.get_thought_signature_by_hash(call_hash) == test_sig

        # Test retrieval by fn name
        assert db.get_thought_signature_by_fn(test_fn) == test_sig

        # Test latest valid retrieval
        assert db.get_latest_valid_thought_signature("gemini-3.8-flash-high") == test_sig

    def test_daemon_restart_survival(self):
        """
        Simulates daemon kill and restart.
        Verifies that a brand new ThoughtSignatureCache instance restores tokens from SQLite.
        """
        cache1 = ThoughtSignatureCache(ttl_seconds=3600)
        call_id = "call_restart_survivor_999"
        sig_data = "U0lHX1JFU1RBUlRfU1VSVklWT1JfVE9LRU4="
        fn_name = "default_api:grep"
        fn_args = {"query": "thought_signature"}

        cache1.store(
            key=call_id,
            signature=sig_data,
            fn_name=fn_name,
            fn_args=fn_args,
            model="gemini-3.8-flash-high"
        )
        assert cache1.get(call_id) == sig_data

        # Simulate daemon restart by instantiating a completely new cache
        cache2 = ThoughtSignatureCache(ttl_seconds=3600)
        # In-memory dictionary is completely empty initially
        assert call_id not in cache2._cache

        # Cache2 should transparently recover the signature from SQLite WAL!
        recovered = cache2.get(call_id)
        assert recovered == sig_data

        # Hash lookup must also recover
        chash = ThoughtSignatureCache.compute_call_hash(fn_name, fn_args)
        assert cache2.get_by_hash(chash) == sig_data

        # Cascading resolver must also resolve
        assert cache2.resolve_signature(call_id=call_id, fn_name=fn_name, fn_args=fn_args) == sig_data

    def test_openai_translator_injects_persisted_signature(self):
        """
        Verifies transform_openai_to_antigravity restores missing thoughtSignature
        from persistent cache when OpenCode client sends bare OpenAI tool_calls.
        """
        test_call_id = "call_opencode_bare_turn_5"
        test_sig = "VkFMSURfVVBTVFJFQU1fQ1JZUFRPX1RPS0VO"
        fn_name = "default_api:read"
        fn_args = {"path": ".config/opencode/opencode.json"}

        # Seed cache
        from prime_gate.translator.thought_cache import thought_sig_cache
        thought_sig_cache.store(
            key=test_call_id,
            signature=test_sig,
            fn_name=fn_name,
            fn_args=fn_args,
            model="gemini-3.8-flash-high"
        )

        # Client payload without any thoughtSignature (as sent by OpenCode)
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
        assert len(contents) >= 3

        # Model turn must contain functionCall WITH thoughtSignature restored!
        model_turn = [c for c in contents if c.get("role") == "model"][0]
        parts = model_turn.get("parts", [])
        fc_part = [p for p in parts if "functionCall" in p][0]

        assert fc_part["functionCall"]["name"] == fn_name
        assert "thoughtSignature" in fc_part
        assert fc_part["thoughtSignature"] == test_sig

    def test_anthropic_translator_injects_signature(self):
        """
        Verifies transform_anthropic_to_antigravity restores missing thoughtSignature
        on Anthropic Messages API tool_use blocks.
        """
        test_call_id = "toolu_anthropic_abc_123"
        test_sig = "QU5USFJPUElDX0NSWVBUT19UT0tFTl9URVNU"
        fn_name = "default_api:search"
        fn_args = {"query": "antigravity"}

        from prime_gate.translator.thought_cache import thought_sig_cache
        thought_sig_cache.store(
            key=test_call_id,
            signature=test_sig,
            fn_name=fn_name,
            fn_args=fn_args,
            model="gemini-3.8-flash-high"
        )

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
        fc_part = [p for p in model_turn.get("parts", []) if "functionCall" in p][0]

        assert fc_part["functionCall"]["name"] == fn_name
        assert "thoughtSignature" in fc_part
        assert fc_part["thoughtSignature"] == test_sig
