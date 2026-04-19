import urllib.error
from unittest.mock import MagicMock, patch

from app import _resolve_restaurant_info


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SHORT_URL = "https://maps.app.goo.gl/abc123"
_PLACE_URL = "https://www.google.com/maps/place/Ramen+Shop/"
_NON_PLACE_URL = "https://www.google.com/"


def _cm(resolved_url):
    """Context-manager mock whose .geturl() returns resolved_url."""
    m = MagicMock()
    m.geturl.return_value = resolved_url
    m.__enter__ = lambda s: s
    m.__exit__ = MagicMock(return_value=False)
    return m


# ---------------------------------------------------------------------------
# Unit tests — _resolve_restaurant_info
# ---------------------------------------------------------------------------


class TestResolveRestaurantInfo:
    def test_no_url_no_text(self):
        assert _resolve_restaurant_info(None, None) is None

    def test_text_with_no_url(self):
        assert _resolve_restaurant_info("just some text, no link", None) is None

    def test_url_not_allowed_host(self):
        assert _resolve_restaurant_info(None, "https://evil.com/maps/place/Foo") is None

    def test_url_resolves_immediately(self):
        with patch("urllib.request.urlopen", return_value=_cm(_PLACE_URL)), patch(
            "time.sleep"
        ):
            result = _resolve_restaurant_info(None, _SHORT_URL)
        assert result == "Ramen Shop"

    def test_url_resolves_after_retry(self):
        side_effects = [_cm(_NON_PLACE_URL), _cm(_NON_PLACE_URL), _cm(_PLACE_URL)]
        with patch("urllib.request.urlopen", side_effect=side_effects), patch(
            "time.sleep"
        ):
            result = _resolve_restaurant_info(None, _SHORT_URL)
        assert result == "Ramen Shop"

    def test_url_never_resolves(self):
        with patch(
            "urllib.request.urlopen", side_effect=[_cm(_NON_PLACE_URL)] * 5
        ), patch("time.sleep"):
            result = _resolve_restaurant_info(None, _SHORT_URL)
        assert result is None

    def test_urlopen_raises(self):
        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("timeout")
        ), patch("time.sleep"):
            result = _resolve_restaurant_info(None, _SHORT_URL)
        assert result is None

    def test_url_in_text_param(self):
        with patch("urllib.request.urlopen", return_value=_cm(_PLACE_URL)), patch(
            "time.sleep"
        ):
            result = _resolve_restaurant_info(f"Check this out: {_SHORT_URL}", None)
        assert result == "Ramen Shop"

    def test_url_param_takes_precedence_over_text(self):
        """url_param is tried before any URL embedded in text_param."""
        url_param = "https://maps.app.goo.gl/xyz"
        place_url_2 = "https://www.google.com/maps/place/Pizza+Palace/"
        with patch("urllib.request.urlopen", return_value=_cm(place_url_2)), patch(
            "time.sleep"
        ):
            result = _resolve_restaurant_info(f"Also here: {_SHORT_URL}", url_param)
        assert result == "Pizza Palace"

    def test_place_name_url_decoded(self):
        url = "https://www.google.com/maps/place/Caf%C3%A9+du+Monde/"
        with patch("urllib.request.urlopen", return_value=_cm(url)), patch(
            "time.sleep"
        ):
            result = _resolve_restaurant_info(None, _SHORT_URL)
        assert result == "Café du Monde"


# ---------------------------------------------------------------------------
# Integration tests — /share-target route
# ---------------------------------------------------------------------------


class TestShareTarget:
    def test_no_params_redirects_to_index(self, client):
        resp = client.get("/share-target")
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")
        with client.session_transaction() as sess:
            assert "share_restaurant_info" not in sess

    def test_valid_url_sets_session_and_redirects(self, client):
        with patch("urllib.request.urlopen", return_value=_cm(_PLACE_URL)), patch(
            "time.sleep"
        ):
            resp = client.get("/share-target", query_string={"url": _SHORT_URL})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")
        with client.session_transaction() as sess:
            assert sess["share_restaurant_info"] == "Ramen Shop"

    def test_unresolvable_url_no_session_key(self, client):
        with patch(
            "urllib.request.urlopen", side_effect=[_cm(_NON_PLACE_URL)] * 5
        ), patch("time.sleep"):
            resp = client.get("/share-target", query_string={"url": _SHORT_URL})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert "share_restaurant_info" not in sess

    def test_urlopen_raises_no_session_key(self, client):
        with patch(
            "urllib.request.urlopen", side_effect=urllib.error.URLError("err")
        ), patch("time.sleep"):
            resp = client.get("/share-target", query_string={"url": _SHORT_URL})
        assert resp.status_code == 302
        with client.session_transaction() as sess:
            assert "share_restaurant_info" not in sess

    def test_requires_login(self, unauthed_client):
        resp = unauthed_client.get("/share-target")
        assert resp.status_code == 302
        assert "login" in resp.headers["Location"]

    def test_session_consumed_on_index(self, client):
        """RESTAURANT_INFO appears on first GET / then is null on refresh (one-shot)."""
        with patch("urllib.request.urlopen", return_value=_cm(_PLACE_URL)), patch(
            "time.sleep"
        ):
            client.get("/share-target", query_string={"url": _SHORT_URL})

        resp1 = client.get("/")
        assert resp1.status_code == 200
        assert b"Ramen Shop" in resp1.data

        resp2 = client.get("/")
        assert resp2.status_code == 200
        assert b'"Ramen Shop"' not in resp2.data
