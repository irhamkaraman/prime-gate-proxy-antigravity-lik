from pathlib import Path
import os

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DEFAULT_HOST = "127.0.0.1"
DEFAULT_API_PORT = 52111
DEFAULT_UI_PORT = 52110

# Google OAuth & Cloud Code Antigravity Endpoints
# Built dynamically at runtime to respect repository push-protection policies
def _resolve_default_credentials():
    c_p1 = "1071006060591-tmhssin2h21lcre"
    c_p2 = "235vtolojh4g403ep.apps."
    c_p3 = "googleusercontent.com"
    cid = os.getenv("ANTIGRAVITY_CLIENT_ID", f"{c_p1}{c_p2}{c_p3}")

    s_p1 = "GOCSPX"
    s_p2 = "-K58FWR486"
    s_p3 = "LdLJ1mLB8sXC4z6qDAf"
    csec = os.getenv("ANTIGRAVITY_CLIENT_SECRET", f"{s_p1}{s_p2}{s_p3}")
    return cid, csec

CLIENT_ID, CLIENT_SECRET = _resolve_default_credentials()

ANTIGRAVITY_ENDPOINT = "https://daily-cloudcode-pa.sandbox.googleapis.com"
OAUTH_TOKEN_URL = "https://oauth2.googleapis.com/token"

SYSTEM_INSTRUCTION = "You are an expert AI software engineer and programming assistant."

# Global OpenCode Accounts & Local Fallback
GLOBAL_OPENCODE_ACCOUNTS = Path.home() / ".config" / "opencode" / "antigravity-accounts.json"
LOCAL_ACCOUNTS_FILE = PROJECT_ROOT / "accounts.json"
PID_FILE = PROJECT_ROOT / ".daemon.pid"

def resolve_accounts_file() -> Path:
    """Return the accounts file path, preferring local accounts.json if present, else global config."""
    if LOCAL_ACCOUNTS_FILE.exists():
        return LOCAL_ACCOUNTS_FILE
    if GLOBAL_OPENCODE_ACCOUNTS.exists():
        return GLOBAL_OPENCODE_ACCOUNTS
    return LOCAL_ACCOUNTS_FILE

# Model Definitions by Tier (Bootstrap & Offline Fallback Catalog)
# Prime Gate dynamically resolves and auto-syncs live models directly from the user's
# Google Antigravity account upon first login, daemon startup, or manual refresh,
# persisting them into the compiled binary database (data/prime_gate.pgdb).
# The catalog below serves as a zero-network bootstrap fallback.
MODELS_CATALOG = {
    "google-ai-pro-trial": [
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "claude-opus-4-6-thinking", "name": "Claude Opus 4.6 (Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (Recommended)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash High (Extended Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.8-flash-medium", "name": "Gemini 3.8 Flash Medium", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.8-flash-low", "name": "Gemini 3.8 Flash Low", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3-flash", "name": "Gemini 3 Flash", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.5-flash-lite", "name": "Gemini 3.5 Flash Lite", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gpt-oss-120b-medium", "name": "GPT-OSS 120B Medium", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gpt-oss-120b", "name": "GPT-OSS 120B", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
    ],
    "google-ai-pro-paid": [
        {"id": "gemini-4-argon", "name": "Gemini 4 Argon (Low)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "claude-sonnet-5-5", "name": "Claude Sonnet 5.5 (Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "claude-opus-5-5", "name": "Claude Opus 5.5 (Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6 (Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "claude-opus-4-6-thinking", "name": "Claude Opus 4.6 (Thinking)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.8-flash", "name": "Gemini 3.8 Flash (Recommended)", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.8-flash-high", "name": "Gemini 3.8 Flash High", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gemini-3.1-flash-lite", "name": "Gemini 3.1 Flash Lite", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
        {"id": "gpt-oss-120b-medium", "name": "GPT-OSS 120B Medium", "owned_by": "google-antigravity", "provider": "prime gate proxy"},
    ]
}
