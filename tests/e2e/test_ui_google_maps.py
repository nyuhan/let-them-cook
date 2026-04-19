"""
UI tests requiring live Google Maps API.

Marked with @pytest.mark.google_maps — need network + GOOGLE_MAPS_API_KEY in .env.
"""

import json

import pytest

from tests.e2e.utils import (
    _card_locators,
    _card_names,
    _click_card,
    _csrf_token,
    _goto,
    _open_dropdown,
    _select_dropdown_option,
)

# Params that Android sends to /share-target when a Maps link is shared.
_SHARE_PARAMS = (
    "title=McDonalds" "&text=https%3A%2F%2Fmaps.app.goo.gl%2FsG5MQkR2AW447amp9"
)


# ---------------------------------------------------------------------------
# Add Restaurant via Google Maps + Refresh (live API)
# ---------------------------------------------------------------------------


class TestGoogleMaps:
    @pytest.mark.google_maps
    def test_add_and_refresh(self, live_server, page):
        page.set_default_timeout(30000)

        _goto(page, live_server)

        # --- Empty state ---
        assert page.locator("text=Nothing here yet").is_visible()

        # Click empty-state Add Restaurant button
        page.locator("button:has-text('Add Restaurant')").first.click()
        modal = page.locator("#restaurant-modal")
        modal.wait_for(state="visible")

        # The <gmp-place-autocomplete> web component uses a closed shadow root,
        # so Playwright cannot interact with its inner <input> directly.
        # Instead we: (1) search for a real restaurant via the Places API,
        # (2) dispatch a synthetic gmp-select event that the app's handler
        # processes identically to a real user selection.
        # This still exercises the real Google Maps fetchFields call.

        # Wait for Google Maps JS to load (Places library must be available)
        page.wait_for_function(
            "() => { try { return typeof google.maps.places.Place === 'function'; } catch(e) { return false; } }",
            timeout=15000,
        )

        # Dispatch synthetic gmp-select with a real Place
        page.evaluate(
            """async () => {
            const el = document.getElementById('place-autocomplete');
            const { Place } = google.maps.places;

            // Find a real restaurant via text search
            const { places } = await Place.searchByText({
                textQuery: 'Pizza Hut',
                fields: ['id'],
                maxResultCount: 1,
            });
            if (!places || places.length === 0) throw new Error('No place found');

            const place = new Place({ id: places[0].id });
            const event = new Event('gmp-select', { bubbles: true });
            event.placePrediction = { toPlace: () => place };
            el.dispatchEvent(event);
        }"""
        )

        # Wait for fetchFields → handler to enable the submit button
        submit = page.locator("#submit-btn")
        page.wait_for_function(
            "!document.getElementById('submit-btn').disabled",
            timeout=15000,
        )
        assert submit.is_enabled()
        assert page.locator("#address-container").is_visible()
        assert page.locator("#opening-hours-container").is_visible()

        # Submit
        submit.click()
        modal.wait_for(state="hidden")

        # Card should appear
        assert _card_locators(page).count() == 1

        # --- Overwrite metadata via backend API ---
        resp = page.request.get(f"{live_server}/api/restaurants")
        rest_id = resp.json()[0]["id"]
        page.request.put(
            f"{live_server}/api/restaurants/{rest_id}",
            data=json.dumps({"name": "Stale Name", "address": "Old Address"}),
            headers={
                "Content-Type": "application/json",
                "X-CSRFToken": _csrf_token(page),
            },
        )

        # Reload page to pick up the stale data
        _goto(page, live_server)

        # --- Refresh Google Maps data ---
        _click_card(page, "Stale Name")
        modal.wait_for(state="visible")
        assert page.locator("#edit-name-display").text_content().strip() == "Stale Name"

        # Click refresh
        page.locator("#refresh-restaurant-btn").click()

        # Wait for success message to appear (it auto-clears after 3 s)
        page.locator("#message:has-text('Refreshed Google Maps data')").wait_for(
            state="visible", timeout=15000
        )

        # Name should be restored from Google Maps (no longer "Stale Name")
        # Give a moment for the modal to re-render after refresh
        page.wait_for_timeout(500)
        refreshed_name = page.locator("#edit-name-display").text_content().strip()
        assert refreshed_name != ""
        assert refreshed_name != "Stale Name"

        # Address should be restored from Google Maps (no longer "Old Address")
        address_container = page.locator("#address-container")
        assert address_container.is_visible()
        refreshed_address = address_container.text_content().strip()
        assert refreshed_address != ""
        assert "Old Address" not in refreshed_address

        # Opening hours should be populated from Google Maps
        opening_hours_container = page.locator("#opening-hours-container")
        assert opening_hours_container.is_visible()

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
