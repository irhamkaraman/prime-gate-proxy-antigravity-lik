import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from ..config import resolve_accounts_file, GLOBAL_OPENCODE_ACCOUNTS, LOCAL_ACCOUNTS_FILE

logger = logging.getLogger("prime_gate.auth")

class AccountManager:
    """Manages Antigravity account configurations, token storage, and round-robin failover."""

    def __init__(self, accounts_file: Optional[Path] = None):
        self.accounts_file = accounts_file or resolve_accounts_file()
        self._active_index = 0

    def load_accounts(self) -> List[Dict[str, Any]]:
        if not self.accounts_file.exists():
            # If local file does not exist but global does, fallback to global
            if GLOBAL_OPENCODE_ACCOUNTS.exists():
                self.accounts_file = GLOBAL_OPENCODE_ACCOUNTS
            else:
                return []
        try:
            with open(self.accounts_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                accounts = data.get("accounts", [])
                return [acc for acc in accounts if acc.get("enabled", True) and acc.get("refreshToken")]
        except Exception as e:
            logger.error(f"Error loading accounts from {self.accounts_file}: {e}")
            return []

    def save_accounts(self, accounts: List[Dict[str, Any]], target_file: Optional[Path] = None) -> bool:
        dest = target_file or self.accounts_file
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            payload = {
                "version": 4,
                "accounts": accounts,
                "activeIndex": 0,
                "activeIndexByFamily": {"claude": 0, "gemini": 0}
            }
            with open(dest, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2)
            self.accounts_file = dest
            return True
        except Exception as e:
            logger.error(f"Failed to save accounts: {e}")
            return False

    def import_from_opencode(self) -> int:
        """Copies accounts from OpenCode config into local accounts.json."""
        if not GLOBAL_OPENCODE_ACCOUNTS.exists():
            return 0
        try:
            with open(GLOBAL_OPENCODE_ACCOUNTS, "r", encoding="utf-8") as f:
                data = json.load(f)
            accounts = data.get("accounts", [])
            if accounts:
                self.save_accounts(accounts, LOCAL_ACCOUNTS_FILE)
                return len(accounts)
        except Exception as e:
            logger.error(f"Failed importing from OpenCode: {e}")
        return 0

    def get_active_account(self) -> Optional[Dict[str, Any]]:
        accounts = self.load_accounts()
        if not accounts:
            return None
        return accounts[self._active_index % len(accounts)]

    def rotate_account(self) -> Optional[Dict[str, Any]]:
        accounts = self.load_accounts()
        if not accounts:
            return None
        self._active_index = (self._active_index + 1) % len(accounts)
        return accounts[self._active_index]
