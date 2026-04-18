"""
E2E tests for the PWA share target flow.

Tests marked google_maps require network + Google Maps API key in .env,
and are excluded from the default test run (see pytest.ini).
"""

import pytest
from tests.e2e.utils import _card_locators


# Params that Android sends to /share-target when a Maps link is shared.
_SHARE_PARAMS = (
    "title=McDonalds" "&text=https%3A%2F%2Fmaps.app.goo.gl%2FsG5MQkR2AW447amp9"
)


class TestShareTargetUI:
    @pytest.mark.google_maps
    def test_share_add_then_reshare_shows_already_exists(self, live_server, page):
        page.set_default_timeout(30000)

        modal = page.locator("#restaurant-modal")

        # --- First visit: modal opens pre-populated, add the restaurant ---

        # Navigate to /share-target. The server resolves the short URL
        # (real network request), stores the place info in session, and
        # redirects to /. Playwright follows the redirect automatically.
        page.goto(
            f"{live_server}/share-target?{_SHARE_PARAMS}",
            wait_until="domcontentloaded",
        )

        # Confirm we landed on / (redirect was followed)
        assert page.url == f"{live_server}/"

        # Modal should open immediately (before the Maps API search finishes)
        modal.wait_for(state="visible")

        # Wait for the Maps JS API + Place.searchByText to populate the form.
        # selectPlaceInForm() sets #place-id when it finds a valid restaurant.
        page.wait_for_function(
            "() => !!document.getElementById('place-id')?.value",
            timeout=20000,
        )

        # Autocomplete element should have a display name
        autocomplete_value = page.evaluate(
            "() => document.getElementById('place-autocomplete')?.value || ''"
        )
        assert autocomplete_value != ""

        # Submit button should be enabled once a place is selected
        submit = page.locator("#submit-btn")
        assert not submit.is_disabled()

        # Submit the form — defaults (rating 5, both) are already set
        submit.click()
        modal.wait_for(state="hidden")

        # Restaurant card should now appear in the list
        assert _card_locators(page).count() == 1

        # --- Second visit: same share link, restaurant already exists ---

        page.goto(
            f"{live_server}/share-target?{_SHARE_PARAMS}",
            wait_until="domcontentloaded",
        )
        modal.wait_for(state="visible")

        page.locator("#message:has-text('Restaurant already exists')").wait_for(
            state="visible", timeout=20000
        )

        # Place ID should be cleared (clearSelection was called)
        assert page.locator("#place-id").input_value() == ""
        # Submit button must remain disabled
        assert submit.is_disabled()
