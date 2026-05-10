import re
import sqlite3
import threading
import time

import pytest
import requests
from werkzeug.serving import make_server

import app as app_module
from app import app as flask_app

_PASSWORD = "letthemcook"
_TEST_SECRET_KEY = "e2e-test-secret-key-fixed"


@pytest.fixture()
def live_server(tmp_path):
    """Start a real Flask server on a random port with a fresh temp DB."""
    app_module.LOGIN_DISABLED = False
    db_path = str(tmp_path / "e2e_test.db")
    app_module.DATABASE = db_path
    flask_app.secret_key = _TEST_SECRET_KEY

    conn = sqlite3.connect(db_path)
    app_module._init_db(conn)
    conn.close()

    flask_app.config.update({"TESTING": False, "WTF_CSRF_ENABLED": True})

    server = make_server("127.0.0.1", 0, flask_app)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    for _ in range(100):
        try:
            requests.get(f"{base_url}/login", timeout=2)
            break
        except requests.exceptions.RequestException:
            time.sleep(0.1)

    yield base_url

    server.shutdown()


@pytest.fixture(scope="session")
def _auth_state():
    """Log in once per session using Flask's test client — no real server needed.

    The signed session cookie is valid for any live_server that uses the same
    _TEST_SECRET_KEY, regardless of port (HTTP cookies are port-agnostic).
    """
    import tempfile

    app_module.LOGIN_DISABLED = False
    original_db = app_module.DATABASE
    with tempfile.TemporaryDirectory() as tmp:
        db_path = f"{tmp}/auth.db"
        app_module.DATABASE = db_path
        flask_app.secret_key = _TEST_SECRET_KEY

        conn = sqlite3.connect(db_path)
        app_module._init_db(conn)
        conn.close()

        with flask_app.test_client() as client:
            login_page = client.get("/login")
            token = _extract_input_csrf_token(login_page.data.decode())
            client.post(
                "/login",
                data={"password": _PASSWORD, "totp_code": "", "csrf_token": token},
            )
            cookie_value = client.get_cookie("session").value

    app_module.DATABASE = original_db
    return {
        "cookies": [
            {
                "name": "session",
                "value": cookie_value,
                "domain": "127.0.0.1",
                "path": "/",
                "expires": -1,
                "httpOnly": False,
                "secure": False,
                "sameSite": "Lax",
            }
        ],
        "origins": [],
    }


@pytest.fixture()
def context(browser, _auth_state):
    """Browser context pre-loaded with a valid session cookie."""
    ctx = browser.new_context(storage_state=_auth_state)
    yield ctx
    ctx.close()


@pytest.fixture()
def seed(live_server):
    """Factory to POST a restaurant to the live server. Returns the data dict."""
    session = requests.Session()
    login_page = session.get(f"{live_server}/login")
    token = _extract_input_csrf_token(login_page.text)
    session.post(
        f"{live_server}/login",
        data={"password": _PASSWORD, "totp_code": "", "csrf_token": token},
    )

    def _seed(**overrides):
        data = {
            "id": "place_abc",
            "name": "Test Restaurant",
            "diningOptions": ["dine-in"],
            "rating": 4,
            "address": "123 Main St",
            "city": "TestCity",
            "mapUri": "https://maps.example.com/place",
            "directionsUri": "https://maps.example.com/dir",
            "priceLevel": 2,
            "notes": "Great place",
            "types": [],
        }
        data.update(overrides)
        resp = session.post(
            f"{live_server}/api/restaurants",
            json=data,
            headers={"X-CSRFToken": token},
        )
        assert resp.status_code == 201, f"Seed failed: {resp.text}"
        return data

    return _seed


@pytest.fixture()
def page(page):
    """Set a shorter default timeout for all e2e tests."""
    page.set_default_timeout(10000)
    return page


@pytest.fixture()
def unauthed_page(browser):
    """Unauthenticated page for testing the login flow."""
    ctx = browser.new_context()
    p = ctx.new_page()
    p.set_default_timeout(10000)
    yield p
    ctx.close()


# ---------------------------------------------------------------------------
# CSRF helpers
# ---------------------------------------------------------------------------


def _extract_input_csrf_token(html):
    """Pull the csrf_token value from a hidden input in HTML."""
    m = re.search(r'<input[^>]*name="csrf_token"[^>]*value="([^"]+)"', html)
    assert m, "csrf_token hidden input not found in HTML"
    return m.group(1)
