import time
import logging
import httpx
from typing import Dict, Any, Tuple
from ..config import CLIENT_ID, CLIENT_SECRET, OAUTH_TOKEN_URL

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

def start_interactive_login(port: int = 53123) -> Dict[str, Any]:
    """Interactive OAuth login flow via browser and temporary localhost callback."""
    import urllib.parse
    import webbrowser
    from http.server import HTTPServer, BaseHTTPRequestHandler

    auth_code_holder = {"code": None, "error": None}

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)

            if "code" in query:
                auth_code_holder["code"] = query["code"][0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"""
                <!DOCTYPE html>
                <html>
                <head><title>Login Sukses - Prime Gate Antigravity</title></head>
                <body style="font-family: sans-serif; background: #0f172a; color: #f8fafc; text-align: center; padding-top: 100px;">
                    <h1 style="color: #38bdf8;">Login Berhasil, Bosss!</h1>
                    <p>Otentikasi Google Antigravity sukses ditangkap. Anda bisa menutup tab ini dan kembali ke terminal.</p>
                </body>
                </html>
                """)
            else:
                auth_code_holder["error"] = query.get("error", ["Unknown error"])[0]
                self.send_response(400)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Login Gagal</h1><p>Gagal mendapatkan authorization code.</p>")

        def log_message(self, format, *args):
            pass  # Silence default HTTP server console noise

    server = HTTPServer(("127.0.0.1", port), OAuthHandler)
    server.timeout = 180  # 3 minutes timeout

    redirect_uri = f"http://127.0.0.1:{port}"
    scope = "https://www.googleapis.com/auth/cloud-platform https://www.googleapis.com/auth/userinfo.email"
    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={CLIENT_ID}&"
        f"redirect_uri={urllib.parse.quote(redirect_uri)}&"
        f"response_type=code&"
        f"scope={urllib.parse.quote(scope)}&"
        f"access_type=offline&"
        f"prompt=consent"
    )

    print(f"\n[Auth] Membuka browser untuk login Google Antigravity...")
    print(f"[Auth] Jika browser tidak terbuka otomatis, salin URL ini ke browser:\n{auth_url}\n")
    webbrowser.open(auth_url)

    while not auth_code_holder["code"] and not auth_code_holder["error"]:
        server.handle_request()

    server.server_close()

    if not auth_code_holder["code"]:
        raise RuntimeError(f"OAuth error: {auth_code_holder['error']}")

    code = auth_code_holder["code"]

    # Exchange code for refresh token
    with httpx.Client(timeout=20.0) as client:
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
            raise RuntimeError(f"Token exchange failed: {resp.text}")

        data = resp.json()
        refresh_token = data.get("refresh_token")
        access_token = data.get("access_token")

        # Get user email
        user_info_resp = client.get(
            "https://www.googleapis.com/oauth2/v2/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        email = user_info_resp.json().get("email", "unknown@gmail.com") if user_info_resp.status_code == 200 else "user@gmail.com"

        return {
            "email": email,
            "refreshToken": refresh_token,
            "projectId": "rising-fact-p41fc",
            "addedAt": int(time.time() * 1000),
            "enabled": True,
        }
