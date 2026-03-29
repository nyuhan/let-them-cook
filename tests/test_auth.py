import sqlite3
import pyotp
import pytest
from bs4 import BeautifulSoup
import app as app_module

_TEST_PASSWORD = "letthemcook"


def _get_flashed(client, category):
    """Return flashed messages of a given category from the session."""
    with client.session_transaction() as session:
        flashes = session.get("_flashes", [])
    return [msg for cat, msg in flashes if cat == category]


def _set_totp_secret(secret):
    conn = sqlite3.connect(app_module.DATABASE)
    conn.execute("UPDATE settings SET totp_secret = ? WHERE id = 1", (secret,))
    conn.commit()
    conn.close()


def _clear_totp_secret():
    _set_totp_secret(None)


# ---------------------------------------------------------------------------
# GET /login
# ---------------------------------------------------------------------------


class TestLoginGet:
    def test_renders_form(self, unauthed_client):
        resp = unauthed_client.get("/login")
        soup = BeautifulSoup(resp.data, "html.parser")
        assert resp.status_code == 200
        assert soup.find("input", {"type": "password", "name": "password"}) is not None

    def test_authenticated_redirects_to_index(self, client):
        resp = client.get("/login")
        assert resp.status_code == 302
        assert resp.location.endswith("/")

    def test_totp_field_shown_when_enabled(self, unauthed_client):
        _set_totp_secret(pyotp.random_base32())
        resp = unauthed_client.get("/login")
        soup = BeautifulSoup(resp.data, "html.parser")
        assert soup.find("input", {"name": "totp_code"}) is not None


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


class TestLoginPost:
    def test_correct_password_redirects_to_index(self, unauthed_client):
        resp = unauthed_client.post(
            "/login", data={"password": _TEST_PASSWORD, "totp_code": ""}
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/")

    def test_wrong_password_redirects_with_flash(self, unauthed_client):
        resp = unauthed_client.post(
            "/login", data={"password": "wrongpassword", "totp_code": ""}
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/login")
        assert _get_flashed(unauthed_client, "error") == ["Invalid credentials."]

    def test_remember_me_sets_persistent_cookie(self, unauthed_client):
        resp = unauthed_client.post(
            "/login",
            data={"password": _TEST_PASSWORD, "totp_code": "", "remember": "on"},
        )
        assert resp.status_code == 302
        assert unauthed_client.get_cookie("remember_token") is not None

    def test_totp_correct_password_and_code(self, unauthed_client):
        secret = pyotp.random_base32()
        _set_totp_secret(secret)
        code = pyotp.TOTP(secret).now()
        resp = unauthed_client.post(
            "/login", data={"password": _TEST_PASSWORD, "totp_code": code}
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/")

    def test_totp_correct_password_wrong_code(self, unauthed_client):
        secret = pyotp.random_base32()
        _set_totp_secret(secret)
        resp = unauthed_client.post(
            "/login", data={"password": _TEST_PASSWORD, "totp_code": "000000"}
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/login")
        assert _get_flashed(unauthed_client, "error") == ["Invalid credentials."]

    def test_totp_wrong_password_correct_code(self, unauthed_client):
        secret = pyotp.random_base32()
        _set_totp_secret(secret)
        code = pyotp.TOTP(secret).now()
        resp = unauthed_client.post(
            "/login", data={"password": "wrongpassword", "totp_code": code}
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/login")
        assert _get_flashed(unauthed_client, "error") == ["Invalid credentials."]


# ---------------------------------------------------------------------------
# GET /logout
# ---------------------------------------------------------------------------


class TestLogout:
    def test_logged_in_redirects_to_login_and_clears_session(self, client):
        client.get("/logout")
        resp = client.get("/")
        assert resp.status_code == 302
        assert resp.location.endswith("/login")

    def test_unauthenticated_redirects_to_login(self, unauthed_client):
        resp = unauthed_client.get("/logout")
        assert resp.status_code == 302
        assert resp.location.endswith("/login")


# ---------------------------------------------------------------------------
# POST /settings — password change
# ---------------------------------------------------------------------------


class TestSettingsPasswordChange:
    def test_wrong_current_password(self, client):
        resp = client.post(
            "/settings",
            data={
                "current_password": "wrongpassword",
                "new_password": "newpassword123",
                "confirm_password": "newpassword123",
            },
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")
        assert _get_flashed(client, "error") == ["Current password is incorrect."]

    def test_new_password_too_short(self, client):
        resp = client.post(
            "/settings",
            data={
                "current_password": _TEST_PASSWORD,
                "new_password": "short",
                "confirm_password": "short",
            },
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")
        assert _get_flashed(client, "error") == [
            "New password must be at least 8 characters."
        ]

    def test_passwords_do_not_match(self, client):
        resp = client.post(
            "/settings",
            data={
                "current_password": _TEST_PASSWORD,
                "new_password": "newpassword123",
                "confirm_password": "differentpassword",
            },
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")
        assert _get_flashed(client, "error") == ["New passwords do not match."]

    def test_valid_change_flashes_success_and_works(self, client, unauthed_client):
        new_pw = "mynewpassword"
        resp = client.post(
            "/settings",
            data={
                "current_password": _TEST_PASSWORD,
                "new_password": new_pw,
                "confirm_password": new_pw,
            },
        )
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")
        assert _get_flashed(client, "success") == ["Password updated successfully."]

        # New password should work for login
        resp2 = unauthed_client.post(
            "/login", data={"password": new_pw, "totp_code": ""}
        )
        assert resp2.status_code == 302
        assert resp2.location.endswith("/")


# ---------------------------------------------------------------------------
# GET /set-up-2fa
# ---------------------------------------------------------------------------


class TestSetup2faGet:
    def test_renders_qr_and_secret(self, client):
        resp = client.get("/set-up-2fa")
        soup = BeautifulSoup(resp.data, "html.parser")
        assert resp.status_code == 200
        assert soup.find("svg") is not None
        assert (
            soup.find("input", {"name": "totp_code", "inputmode": "numeric"})
            is not None
        )

    def test_reuses_provisional_secret_on_second_visit(self, client):
        client.get("/set-up-2fa")
        with client.session_transaction() as session:
            secret1 = session["provisional_totp_secret"]
        client.get("/set-up-2fa")
        with client.session_transaction() as session:
            secret2 = session["provisional_totp_secret"]
        assert secret1 == secret2


# ---------------------------------------------------------------------------
# POST /set-up-2fa
# ---------------------------------------------------------------------------


class TestSetup2faPost:
    def test_correct_code_saves_secret_and_redirects(self, client):
        client.get("/set-up-2fa")
        with client.session_transaction() as session:
            secret = session["provisional_totp_secret"]
        code = pyotp.TOTP(secret).now()
        resp = client.post("/set-up-2fa", data={"totp_code": code})
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")

        # Secret is now in the DB
        conn = sqlite3.connect(app_module.DATABASE)
        row = conn.execute("SELECT totp_secret FROM settings WHERE id = 1").fetchone()
        conn.close()
        assert row[0] == secret

        # provisional_totp_secret is cleared from session
        with client.session_transaction() as session:
            assert "provisional_totp_secret" not in session

    def test_wrong_code_flashes_error(self, client):
        client.get("/set-up-2fa")
        resp = client.post("/set-up-2fa", data={"totp_code": "000000"})
        assert resp.status_code == 302
        assert resp.location.endswith("/set-up-2fa")
        assert _get_flashed(client, "set_up_2fa_error") == [
            "Invalid code. Please try again."
        ]

        # Secret must NOT be saved
        conn = sqlite3.connect(app_module.DATABASE)
        row = conn.execute("SELECT totp_secret FROM settings WHERE id = 1").fetchone()
        conn.close()
        assert row[0] is None

    def test_no_provisional_secret_in_session_redirects(self, client):
        resp = client.post("/set-up-2fa", data={"totp_code": "123456"})
        assert resp.status_code == 302
        assert resp.location.endswith("/set-up-2fa")


# ---------------------------------------------------------------------------
# POST /disable-2fa
# ---------------------------------------------------------------------------


class TestDisable2fa:
    def test_correct_code_clears_secret(self, client):
        secret = pyotp.random_base32()
        _set_totp_secret(secret)
        code = pyotp.TOTP(secret).now()
        resp = client.post("/disable-2fa", data={"totp_code": code})
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")

        conn = sqlite3.connect(app_module.DATABASE)
        row = conn.execute("SELECT totp_secret FROM settings WHERE id = 1").fetchone()
        conn.close()
        assert row[0] is None

    def test_wrong_code_flashes_error_and_preserves_secret(self, client):
        secret = pyotp.random_base32()
        _set_totp_secret(secret)
        resp = client.post("/disable-2fa", data={"totp_code": "000000"})
        assert resp.status_code == 302
        assert resp.location.endswith("/settings")
        assert _get_flashed(client, "totp_error") == ["Invalid authenticator code."]

        conn = sqlite3.connect(app_module.DATABASE)
        row = conn.execute("SELECT totp_secret FROM settings WHERE id = 1").fetchone()
        conn.close()
        assert row[0] == secret
