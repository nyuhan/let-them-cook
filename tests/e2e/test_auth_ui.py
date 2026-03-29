"""E2E auth tests: login, logout, 2FA setup/disable, and LOGIN_DISABLED mode."""

import sqlite3
import pyotp
import pytest

import app as app_module

_PASSWORD = "letthemcook"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _set_totp_in_db(secret):
    """Write a TOTP secret (or NULL) into the live test DB."""
    conn = sqlite3.connect(app_module.DATABASE)
    conn.execute("UPDATE settings SET totp_secret = ? WHERE id = 1", (secret,))
    conn.commit()
    conn.close()


def _clear_totp_from_db():
    _set_totp_in_db(None)


# ---------------------------------------------------------------------------
# TestLoginPage
# ---------------------------------------------------------------------------


class TestLoginPage:
    def test_unauthenticated_redirect_shows_login(self, unauthed_page, live_server):
        unauthed_page.goto(live_server + "/")
        unauthed_page.wait_for_url(f"{live_server}/login")
        assert unauthed_page.locator("input[name='password']").is_visible()

    def test_wrong_password_shows_error(self, unauthed_page, live_server):
        unauthed_page.goto(live_server + "/login")
        unauthed_page.fill("input[name='password']", "wrongpassword")
        unauthed_page.click("button[type='submit']")
        unauthed_page.wait_for_url(f"{live_server}/login")
        assert "Invalid credentials" in unauthed_page.locator("div.bg-red-50").text_content()

    def test_correct_password_lands_on_index(self, unauthed_page, live_server):
        unauthed_page.goto(live_server + "/login")
        unauthed_page.fill("input[name='password']", _PASSWORD)
        unauthed_page.click("button[type='submit']")
        unauthed_page.wait_for_url(f"{live_server}/")

    def test_totp_field_hidden_without_2fa(self, unauthed_page, live_server):
        unauthed_page.goto(live_server + "/login")
        assert not unauthed_page.locator("input[name='totp_code']").is_visible()

    def test_totp_field_visible_with_2fa(self, unauthed_page, live_server):
        secret = pyotp.random_base32()
        _set_totp_in_db(secret)
        try:
            unauthed_page.goto(live_server + "/login")
            assert unauthed_page.locator("input[name='totp_code']").is_visible()
        finally:
            _clear_totp_from_db()

    def test_totp_wrong_code_stays_on_login(self, unauthed_page, live_server):
        secret = pyotp.random_base32()
        _set_totp_in_db(secret)
        try:
            unauthed_page.goto(live_server + "/login")
            unauthed_page.fill("input[name='password']", _PASSWORD)
            unauthed_page.fill("input[name='totp_code']", "000000")
            unauthed_page.click("button[type='submit']")
            unauthed_page.wait_for_url(f"{live_server}/login")
            assert "Invalid credentials" in unauthed_page.locator("div.bg-red-50").text_content()
        finally:
            _clear_totp_from_db()

    def test_totp_correct_code_logs_in(self, unauthed_page, live_server):
        secret = pyotp.random_base32()
        _set_totp_in_db(secret)
        try:
            unauthed_page.goto(live_server + "/login")
            unauthed_page.fill("input[name='password']", _PASSWORD)
            unauthed_page.fill("input[name='totp_code']", pyotp.TOTP(secret).now())
            unauthed_page.click("button[type='submit']")
            unauthed_page.wait_for_url(f"{live_server}/")
        finally:
            _clear_totp_from_db()

    def test_remember_me_sets_cookie(self, unauthed_page, live_server):
        unauthed_page.goto(live_server + "/login")
        unauthed_page.fill("input[name='password']", _PASSWORD)
        unauthed_page.check("input[name='remember']")
        unauthed_page.click("button[type='submit']")
        unauthed_page.wait_for_url(f"{live_server}/")
        cookies = {c["name"]: c for c in unauthed_page.context.cookies()}
        assert "remember_token" in cookies


# ---------------------------------------------------------------------------
# TestLogoutUI
# ---------------------------------------------------------------------------


class TestLogoutUI:
    def test_logout_clears_session(self, page, live_server):
        page.goto(live_server + "/")
        page.wait_for_url(f"{live_server}/")
        page.goto(live_server + "/logout")
        page.wait_for_url(f"{live_server}/login")
        page.goto(live_server + "/")
        page.wait_for_url(f"{live_server}/login")


# ---------------------------------------------------------------------------
# TestSetup2faUI
# ---------------------------------------------------------------------------


class TestSetup2faUI:
    def test_setup_page_shows_qr_and_input(self, page, live_server):
        page.goto(live_server + "/setup-2fa")
        assert page.locator("svg").is_visible()
        assert page.locator("input[name='totp_code']").is_visible()

    def test_wrong_code_shows_error(self, page, live_server):
        page.goto(live_server + "/setup-2fa")
        page.fill("input[name='totp_code']", "000000")
        page.click("button[type='submit']")
        page.wait_for_url(f"{live_server}/setup-2fa")
        assert "Invalid code" in page.locator("div.bg-red-50").text_content()

    def test_correct_code_enables_2fa(self, page, live_server):
        page.goto(live_server + "/setup-2fa")
        secret = page.locator("code").text_content().strip()
        page.fill("input[name='totp_code']", pyotp.TOTP(secret).now())
        page.click("button[type='submit']")
        page.wait_for_url(f"{live_server}/settings")
        assert "Enabled" in page.locator("p.text-green-700").text_content()


# ---------------------------------------------------------------------------
# TestDisable2faUI
# ---------------------------------------------------------------------------


class TestDisable2faUI:
    def test_wrong_totp_shows_error(self, page, live_server):
        secret = pyotp.random_base32()
        _set_totp_in_db(secret)
        page.goto(live_server + "/settings")
        page.click("#disable-2fa-btn")
        page.locator("#disable-2fa-totp").fill("000000")
        page.locator("#disable-2fa-modal button[type='submit']").click()
        page.wait_for_url(f"{live_server}/settings")
        # JS auto-opens modal when totp_error flash is present
        assert page.locator("#disable-2fa-modal").is_visible()
        assert "Invalid authenticator code" in page.locator("#disable-2fa-modal").text_content()

    def test_correct_totp_disables_2fa(self, page, live_server):
        secret = pyotp.random_base32()
        _set_totp_in_db(secret)
        page.goto(live_server + "/settings")
        page.click("#disable-2fa-btn")
        page.locator("#disable-2fa-totp").fill(pyotp.TOTP(secret).now())
        page.locator("#disable-2fa-modal button[type='submit']").click()
        page.wait_for_url(f"{live_server}/settings")
        assert "Not enabled" in page.locator("main").text_content()


# ---------------------------------------------------------------------------
# TestLoginDisabled
# ---------------------------------------------------------------------------


@pytest.fixture()
def login_disabled_server(live_server):
    original = app_module.LOGIN_DISABLED
    app_module.LOGIN_DISABLED = True
    yield live_server
    app_module.LOGIN_DISABLED = original


class TestLoginDisabled:
    def test_index_accessible_without_login(self, unauthed_page, login_disabled_server):
        unauthed_page.goto(login_disabled_server + "/")
        assert "/login" not in unauthed_page.url

    def test_settings_and_setup_2fa_return_404(self, unauthed_page, login_disabled_server):
        resp = unauthed_page.request.get(login_disabled_server + "/settings")
        assert resp.status == 404
        resp2 = unauthed_page.request.get(login_disabled_server + "/setup-2fa")
        assert resp2.status == 404
