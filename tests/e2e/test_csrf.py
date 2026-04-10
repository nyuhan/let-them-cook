"""E2E tests verifying CSRF protection is enforced."""

import threading
import sqlite3
import requests
import time
import pytest
from werkzeug.serving import make_server

from app import app as flask_app
import app as app_module

_PASSWORD = "letthemcook"
_TEST_SECRET_KEY = "e2e-csrf-test-key"


@pytest.fixture()
def csrf_server(tmp_path):
    """Live Flask server with CSRF protection enabled."""
    db_path = str(tmp_path / "csrf_test.db")
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
    flask_app.config["WTF_CSRF_ENABLED"] = False


# ---------------------------------------------------------------------------
# Form submissions without CSRF token are rejected
# ---------------------------------------------------------------------------


class TestFormCSRF:
    def test_login_without_csrf_token_rejected(self, csrf_server):
        """POST /login without a CSRF token returns 400."""
        resp = requests.post(
            f"{csrf_server}/login",
            data={"password": _PASSWORD, "totp_code": ""},
        )
        assert resp.status_code == 400

    def test_login_with_csrf_token_succeeds(self, csrf_server):
        """POST /login with a valid CSRF token succeeds."""
        s = requests.Session()
        login_page = s.get(f"{csrf_server}/login")
        token = _extract_csrf_token(login_page.text)
        resp = s.post(
            f"{csrf_server}/login",
            data={"password": _PASSWORD, "totp_code": "", "csrf_token": token},
        )
        # Successful login redirects to index
        assert resp.status_code == 200
        assert "Let Them Cook" in resp.text

    def test_settings_post_without_csrf_token_rejected(self, csrf_server):
        """POST /settings without a CSRF token returns 400."""
        s = _login_session(csrf_server)
        resp = s.post(
            f"{csrf_server}/settings",
            data={
                "current_password": _PASSWORD,
                "new_password": "newpassword1",
                "confirm_password": "newpassword1",
            },
            allow_redirects=False,
        )
        assert resp.status_code == 400


# ---------------------------------------------------------------------------
# API calls without CSRF token are rejected
# ---------------------------------------------------------------------------


class TestAPICSRF:
    def test_post_restaurant_without_csrf_rejected(self, csrf_server):
        """POST /api/restaurants without X-CSRFToken returns 400."""
        s = _login_session(csrf_server)
        resp = s.post(
            f"{csrf_server}/api/restaurants",
            json={
                "id": "place_csrf_test",
                "name": "CSRF Test",
                "diningOptions": "dine-in",
                "rating": 3,
                "address": "1 St",
                "city": "City",
            },
        )
        assert resp.status_code == 400

    def test_post_restaurant_with_csrf_succeeds(self, csrf_server):
        """POST /api/restaurants with X-CSRFToken succeeds."""
        s = _login_session(csrf_server)
        token = _get_meta_csrf_token(s, csrf_server)
        resp = s.post(
            f"{csrf_server}/api/restaurants",
            json={
                "id": "place_csrf_ok",
                "name": "CSRF OK",
                "diningOptions": "dine-in",
                "rating": 4,
                "address": "2 St",
                "city": "City",
            },
            headers={"X-CSRFToken": token},
        )
        assert resp.status_code == 201

    def test_put_restaurant_without_csrf_rejected(self, csrf_server):
        """PUT /api/restaurants/<id> without X-CSRFToken returns 400."""
        s = _login_session(csrf_server)
        token = _get_meta_csrf_token(s, csrf_server)
        # Seed a restaurant first
        s.post(
            f"{csrf_server}/api/restaurants",
            json={
                "id": "place_put",
                "name": "Put Test",
                "diningOptions": "dine-in",
                "rating": 3,
                "address": "3 St",
                "city": "City",
            },
            headers={"X-CSRFToken": token},
        )
        # PUT without token
        resp = s.put(
            f"{csrf_server}/api/restaurants/place_put",
            json={"notes": "updated"},
        )
        assert resp.status_code == 400

    def test_delete_restaurant_without_csrf_rejected(self, csrf_server):
        """DELETE /api/restaurants/<id> without X-CSRFToken returns 400."""
        s = _login_session(csrf_server)
        token = _get_meta_csrf_token(s, csrf_server)
        # Seed
        s.post(
            f"{csrf_server}/api/restaurants",
            json={
                "id": "place_del",
                "name": "Del Test",
                "diningOptions": "dine-in",
                "rating": 3,
                "address": "4 St",
                "city": "City",
            },
            headers={"X-CSRFToken": token},
        )
        # DELETE without token
        resp = s.delete(f"{csrf_server}/api/restaurants/place_del")
        assert resp.status_code == 400

    def test_get_requests_exempt_from_csrf(self, csrf_server):
        """GET requests should not require a CSRF token."""
        s = _login_session(csrf_server)
        resp = s.get(f"{csrf_server}/api/restaurants")
        assert resp.status_code == 200
        resp = s.get(f"{csrf_server}/api/cities")
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Browser: CSRF token present in meta tag and forms
# ---------------------------------------------------------------------------


class TestCSRFTokenInPage:
    def test_meta_tag_present_on_index(self, csrf_server, browser):
        """The index page contains a csrf-token meta tag."""
        ctx, page = _browser_login(csrf_server, browser)
        page.goto(f"{csrf_server}/")
        meta = page.locator('meta[name="csrf-token"]')
        assert meta.count() == 1
        assert len(meta.get_attribute("content")) > 10
        ctx.close()

    def test_meta_tag_present_on_login(self, csrf_server, browser):
        """The login page contains a csrf-token meta tag."""
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(10000)
        page.goto(f"{csrf_server}/login")
        meta = page.locator('meta[name="csrf-token"]')
        assert meta.count() == 1
        assert len(meta.get_attribute("content")) > 10
        ctx.close()

    def test_hidden_csrf_field_in_login_form(self, csrf_server, browser):
        """The login form contains a hidden csrf_token input."""
        ctx = browser.new_context()
        page = ctx.new_page()
        page.set_default_timeout(10000)
        page.goto(f"{csrf_server}/login")
        hidden = page.locator('input[name="csrf_token"][type="hidden"]')
        assert hidden.count() == 1
        assert len(hidden.get_attribute("value")) > 10
        ctx.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_csrf_token(html):
    """Pull the csrf_token value from a hidden input in HTML."""
    import re

    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', html)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', html)
    assert m, "csrf_token hidden input not found in HTML"
    return m.group(1)


def _get_meta_csrf_token(session, base_url):
    """Fetch the index page and extract the CSRF token from the meta tag."""
    import re

    resp = session.get(f"{base_url}/")
    m = re.search(r'<meta name="csrf-token" content="([^"]+)"', resp.text)
    assert m, "csrf-token meta tag not found"
    return m.group(1)


def _login_session(base_url):
    """Return a requests.Session logged in via the CSRF-protected login form."""
    s = requests.Session()
    login_page = s.get(f"{base_url}/login")
    token = _extract_csrf_token(login_page.text)
    s.post(
        f"{base_url}/login",
        data={"password": _PASSWORD, "totp_code": "", "csrf_token": token},
    )
    return s


def _browser_login(base_url, browser):
    """Log in via the browser and return (context, page)."""
    ctx = browser.new_context()
    page = ctx.new_page()
    page.set_default_timeout(10000)
    page.goto(f"{base_url}/login")
    page.fill("input[name='password']", _PASSWORD)
    page.click("button[type='submit']")
    page.wait_for_url(f"{base_url}/")
    return ctx, page
