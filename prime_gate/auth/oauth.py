import time
import logging
import httpx
from typing import Dict, Any, Tuple
from ..config import CLIENT_ID, CLIENT_SECRET, OAUTH_TOKEN_URL, DEFAULT_UI_PORT

logger = logging.getLogger("prime_gate.oauth")

# In-memory token cache: email -> (access_token, expires_at_timestamp)
_TOKEN_CACHE: Dict[str, Tuple[str, float]] = {}

async def get_access_token(account: Dict[str, Any]) -> str:
    """Retrieve or refresh Google OAuth2 access token for the given account."""
    email = account.get("email", "default")
    now = time.time()

    if email in _TOKEN_CACHE:
        token, expires_at = _TOKEN_CACHE[email]
        if expires_at > now + 60:
            return token

    refresh_token = account.get("refreshToken")
    if not refresh_token:
        raise ValueError(f"No refreshToken found for account {email}")

    logger.info(f"Refreshing Google access token for {email}...")

    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "refresh_token": refresh_token,
                "grant_type": "refresh_token",
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Google token refresh failed for {email} ({resp.status_code}): {resp.text}")

        data = resp.json()
        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError(f"Google token response missing access_token: {data}")

        expires_in = data.get("expires_in", 3600)
        _TOKEN_CACHE[email] = (access_token, now + (expires_in - 120))
        logger.info(f"Access token refreshed successfully for {email}")
        return access_token

def get_auth_url(port: int = 53123) -> str:
    """Generate the Google OAuth2 consent URL for Antigravity access."""
    import urllib.parse
    redirect_uri = f"http://127.0.0.1:{port}"
    scope = "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email"
    return (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(scope)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

def start_interactive_login(port: int = 53123) -> Dict[str, Any]:
    """Interactive OAuth login flow via browser and temporary localhost callback."""
    import urllib.parse
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler

    auth_code_holder = {"code": None, "error": None}

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            # Ignore favicon or asset requests
            if parsed.path.endswith("favicon.ico"):
                self.send_response(204)
                self.end_headers()
                return

            query = urllib.parse.parse_qs(parsed.query)

            if "code" in query:
                auth_code_holder["code"] = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Authentication Successful - Prime Gate</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background: #130f0c;
            color: #f5f5f4;
            display: flex;
            align-items: center;
            justify-content: center;
            min-height: 100vh;
            padding: 24px;
        }}
        .auth-card {{
            background: #1b1613;
            border: 1px solid rgba(168, 162, 158, 0.18);
            border-radius: 16px;
            padding: 40px 36px;
            max-width: 480px;
            width: 100%;
            text-align: center;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.6);
        }}
        .icon-circle {{
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.35);
            color: #10b981;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            margin-bottom: 20px;
        }}
        h1 {{
            font-size: 24px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: -0.02em;
            margin-bottom: 8px;
        }}
        p.subtitle {{
            font-size: 14px;
            color: #a8a29e;
            line-height: 1.6;
            margin-bottom: 28px;
        }}
        .btn-group {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}
        .btn-primary {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            gap: 8px;
            background: #d97706;
            color: #ffffff;
            font-size: 14px;
            font-weight: 600;
            padding: 13px 24px;
            border-radius: 10px;
            text-decoration: none;
            transition: all 0.2s ease;
            box-shadow: 0 4px 14px rgba(217, 119, 6, 0.35);
        }}
        .btn-primary:hover {{
            background: #b45309;
            transform: translateY(-1px);
        }}
        .btn-secondary {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(168, 162, 158, 0.2);
            color: #d6d3d1;
            font-size: 13px;
            padding: 11px 20px;
            border-radius: 10px;
            cursor: pointer;
            text-decoration: none;
            transition: all 0.2s ease;
        }}
        .btn-secondary:hover {{
            background: rgba(255, 255, 255, 0.09);
            color: #ffffff;
        }}
        .footer-hint {{
            font-size: 12px;
            color: #78716c;
            margin-top: 24px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
        }}
    </style>
</head>
<body>
    <div class="auth-card">
        <div class="icon-circle">
            <svg width="28" height="28" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2.5" d="M5 13l4 4L19 7"/>
            </svg>
        </div>
        <h1>Authentication Successful</h1>
        <p class="subtitle">Google Antigravity authentication was captured successfully. Your account is now active and ready.</p>
        <div class="btn-group">
            <a href="http://127.0.0.1:{DEFAULT_UI_PORT}" class="btn-primary" id="openDashboardBtn">
                Go to Dashboard &rarr;
            </a>
            <button onclick="window.close()" class="btn-secondary">
                Close This Window
            </button>
        </div>
        <p class="footer-hint">Prime Gate Gateway &bull; 127.0.0.1:52111</p>
    </div>
</body>
</html>""".encode("utf-8"))
            elif "error" in query:
                auth_code_holder["error"] = query["error"][0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                err_msg = query['error'][0]
                self.wfile.write(f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Authentication Cancelled - Prime Gate</title>
    <style>
        body {{ font-family: sans-serif; background: #130f0c; color: #f5f5f4; display: flex; align-items: center; justify-content: center; min-height: 100vh; padding: 24px; margin: 0; }}
        .card {{ background: #1b1613; border: 1px solid rgba(244, 63, 94, 0.3); border-radius: 16px; padding: 36px; max-width: 440px; text-align: center; }}
        h1 {{ color: #fb7185; font-size: 22px; margin-bottom: 12px; }}
        p {{ color: #a8a29e; font-size: 14px; margin-bottom: 24px; font-family: monospace; }}
        a {{ display: inline-block; padding: 10px 20px; background: #241d18; border: 1px solid rgba(168, 162, 158, 0.3); color: #fff; text-decoration: none; border-radius: 8px; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="card">
        <h1>Authentication Cancelled</h1>
        <p>Error: {err_msg}</p>
        <a href="http://127.0.0.1:{DEFAULT_UI_PORT}">Return to Dashboard &rarr;</a>
    </div>
</body>
</html>""".encode("utf-8"))
            else:
                # Browser connected without code/error (pre-connection or manual visit)
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<!DOCTYPE html><html><body style='font-family:sans-serif;background:#130f0c;color:#a8a29e;text-align:center;padding-top:80px;'><h1>Prime Gate OAuth Listener Active</h1><p>Waiting for Google authentication response...</p></body></html>")

        def log_message(self, format, *args):
            pass  # Silence default HTTP server console noise

    class ReusableHTTPServer(HTTPServer):
        allow_reuse_address = True

    server = ReusableHTTPServer(("127.0.0.1", port), OAuthHandler)
    server.timeout = 2.0  # Check loop every 2 seconds

    redirect_uri = f"http://127.0.0.1:{port}"
    auth_url = get_auth_url(port=port)

    print(f"\n[Auth] Opening browser for Google Antigravity authentication...")
    print(f"[Auth] If the browser does not open automatically, copy this URL to your browser:\n{auth_url}\n")
    try:
        webbrowser.open(auth_url)
    except Exception as e:
        logger.warning(f"Could not open browser automatically: {e}")

    deadline = time.time() + 180  # 3 minutes deadline
    try:
        while not auth_code_holder["code"] and not auth_code_holder["error"]:
            if time.time() > deadline:
                auth_code_holder["error"] = "OAuth login timed out. Authorization not received within 3 minutes."
                break
            server.handle_request()
    finally:
        server.server_close()

    if not auth_code_holder["code"]:
        raise RuntimeError(f"OAuth error: {auth_code_holder['error'] or 'Authentication was not completed.'}")

    code = auth_code_holder["code"]

    # Exchange code for refresh token
    with httpx.Client(timeout=25.0) as client:
        resp = client.post(
            OAUTH_TOKEN_URL,
            data={
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )

        if resp.status_code != 200:
            raise RuntimeError(f"Token exchange failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        refresh_token = data.get("refresh_token")
        access_token = data.get("access_token")

        if not access_token:
            raise RuntimeError(f"Google token response missing access token: {data}")

        # Get user email
        user_info_resp = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        email = user_info_resp.json().get("email", "unknown@gmail.com") if user_info_resp.status_code == 200 else "user@gmail.com"

        if not refresh_token:
            # Fallback to existing refresh token if previously registered
            from .accounts import AccountManager
            mgr = AccountManager()
            for existing in mgr.load_accounts():
                if existing.get("email") == email and existing.get("refreshToken"):
                    refresh_token = existing.get("refreshToken")
                    logger.info(f"Re-using existing refreshToken for {email}")
                    break

        if not refresh_token:
            raise RuntimeError(
                f"Google did not return a refresh token for {email}. "
                f"Please ensure you grant offline permissions, or use 'Quick Import from OpenCode Config'."
            )

        return {
            "email": email,
            "refreshToken": refresh_token,
            "projectId": "rising-fact-p41fc",
            "addedAt": int(time.time() * 1000),
            "enabled": True,
        }

