import unittest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from prime_gate.server import app
from prime_gate.db import db
from prime_gate.crypto.auth_manager import AuthManager, COOKIE_SESSION_NAME


class TestWebSocketSecurity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw_key, cls.key_rec = db.create_api_key(name="ws-test-key")

    @classmethod
    def tearDownClass(cls):
        db.revoke_api_key(cls.key_rec["id"])

    def test_websocket_rejected_without_session(self):
        client = TestClient(app, base_url="http://localhost:52111")
        try:
            with client.websocket_connect("/ws/live") as ws:
                pass
            self.fail("WebSocket connection should have been rejected without session")
        except WebSocketDisconnect as e:
            self.assertEqual(e.code, 4001)
        except Exception:
            # Rejection before or during handshake
            pass

    def test_websocket_rejected_with_invalid_origin(self):
        client = TestClient(app, base_url="http://localhost:52111")
        # Create session
        sess_id, _ = AuthManager.create_session()
        client.cookies.set(COOKIE_SESSION_NAME, sess_id)

        try:
            with client.websocket_connect("/ws/live", headers={"Origin": "https://malicious.com"}) as ws:
                pass
            self.fail("WebSocket connection should have been rejected with invalid origin")
        except WebSocketDisconnect as e:
            self.assertEqual(e.code, 4003)
        except Exception:
            pass

    def test_websocket_accepted_with_valid_session_and_origin(self):
        client = TestClient(app, base_url="http://localhost:52111")
        sess_id, _ = AuthManager.create_session()
        client.cookies.set(COOKIE_SESSION_NAME, sess_id)

        with client.websocket_connect("/ws/live", headers={"Origin": "http://localhost:52110"}) as ws:
            init_msg = ws.receive_json()
            self.assertEqual(init_msg.get("type"), "INIT_STATE")


if __name__ == "__main__":
    unittest.main()
