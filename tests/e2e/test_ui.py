"""
UI integration tests using Playwright.

Most tests are offline (no external APIs).
Tests marked google_maps require network + Google Maps API key in .env.
"""

import json
import re
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _card_locators(page):
    """Return locators for all restaurant cards in the list."""
    return page.locator("#list .bg-white.rounded-lg")


def _card_names(page):
    """Return a list of visible restaurant names from cards."""
    cards = _card_locators(page)
    count = cards.count()
    names = []
    for i in range(count):
        name_el = cards.nth(i).locator("span.text-lg.font-bold")
        names.append(name_el.text_content().strip())
    return names


def _goto(page, url):
    """Navigate and wait for DOM + API data to load (skip waiting for external scripts)."""
    page.goto(url, wait_until="domcontentloaded")
    page.wait_for_load_state("networkidle")


def _csrf_token(page):
    """Extract the CSRF token from the page's meta tag."""
    return page.locator('meta[name="csrf-token"]').get_attribute("content")


def _click_card(page, name):
    """Click a restaurant card by name to trigger enterEditMode.

    The <a> title link has stopPropagation, so we dispatch a click event
    directly on the card element to reliably trigger the handler — avoids
    flakiness on slow CI runners.
    """
    card = page.locator(
        "#list .bg-white.rounded-lg", has=page.locator(f"text='{name}'")
    )
    card.dispatch_event("click")


def _open_dropdown(page, trigger_default_text):
    """Open a filter dropdown by its default trigger text."""
    page.locator(f".dropdown-trigger[data-default='{trigger_default_text}']").click()


def _select_dropdown_option(page, trigger_default_text, option_value):
    """Select an option in a filter dropdown."""
    _open_dropdown(page, trigger_default_text)
    container = page.locator(
        f".dropdown-trigger[data-default='{trigger_default_text}']"
    ).locator("..")
    container.locator(f".dropdown-menu button[data-value='{option_value}']").click()


# ---------------------------------------------------------------------------
# Empty State Renders
# ---------------------------------------------------------------------------


class TestEmptyState:
    def test_empty_state_renders(self, live_server, page):
        _goto(page, live_server)

        assert page.locator("text=Nothing here yet").is_visible()
        assert page.locator(
            "#empty-state-add-btn, button:has-text('Add Restaurant')"
        ).first.is_visible()

        # City dropdown should only have "Any"
        _open_dropdown(page, "City")
        city_options = page.locator("#city-filter-options button")
        assert city_options.count() == 1
        assert city_options.first.text_content().strip() == "Any"

        # Cuisine dropdown should only have "Any"
        _open_dropdown(page, "Cuisine")
        cuisine_options = page.locator("#cuisine-filter-options button")
        assert cuisine_options.count() == 1
        assert cuisine_options.first.text_content().strip() == "Any"


# ---------------------------------------------------------------------------
# Restaurant Cards Render
# ---------------------------------------------------------------------------


class TestCardsRender:
    def test_cards_render_with_data(self, live_server, seed, page):
        seed(
            id="r1",
            name="Burger Palace",
            city="Amsterdam",
            diningOptions="dine-in",
            rating=5,
            priceLevel=1,
            notes="Best burgers in town",
        )
        seed(
            id="r2",
            name="Pasta House",
            city="Zurich",
            diningOptions="delivery",
            rating=3,
            priceLevel=3,
            notes="",
            dishes=[
                {"name": "Carbonara", "rating": 1},
                {"name": "Pesto Penne", "rating": 0},
            ],
        )
        seed(
            id="r3",
            name="Sushi Bar",
            city="Amsterdam",
            diningOptions="both",
            rating=4,
            priceLevel=2,
        )

        _goto(page, live_server)

        cards = _card_locators(page)
        assert cards.count() == 3

        # Verify individual card content
        names = _card_names(page)
        assert "Burger Palace" in names
        assert "Pasta House" in names
        assert "Sushi Bar" in names

        # Card with notes should show notes text
        assert page.locator("text=Best burgers in town").is_visible()

        # Card with dishes should show dish names
        assert page.locator("text=Carbonara").is_visible()
        assert page.locator("text=Pesto Penne").is_visible()

    def test_cuisine_badges_shown(self, live_server, seed, page):
        seed(
            id="c1",
            name="Sushi Place",
            types=["japanese_restaurant", "sushi_restaurant", "restaurant"],
        )
        _goto(page, live_server)

        card = page.locator(
            "#list .bg-white.rounded-lg", has=page.locator("text='Sushi Place'")
        )
        # "Japanese" should appear as a badge (japanese_restaurant → Japanese)
        assert card.locator("text=Japanese").is_visible()

    def test_no_cuisine_badges_when_no_types(self, live_server, seed, page):
        seed(
            id="c2", name="Mystery Spot", types=["restaurant"]
        )  # "restaurant" maps to null → no badge
        _goto(page, live_server)

        card = page.locator(
            "#list .bg-white.rounded-lg", has=page.locator("text='Mystery Spot'")
        )
        # No badge row should be present
        assert card.locator(".rounded-full.bg-indigo-50").count() == 0


# ---------------------------------------------------------------------------
# Add Restaurant Modal — Open and Close
# ---------------------------------------------------------------------------


class TestAddModalOpenClose:
    def test_modal_open_and_close(self, live_server, seed, page):
        seed()  # need at least one so we don't get empty state
        _goto(page, live_server)

        # Open modal via header button
        page.locator("#add-restaurant-btn").click()
        modal = page.locator("#restaurant-modal")
        assert modal.is_visible()
        assert page.locator("#modal-title").text_content().strip() == "Add Restaurant"

        # Submit button should be disabled
        submit = page.locator("#submit-btn")
        assert submit.is_disabled()

        # Default type is both (has active ring classes)
        both_btn = page.locator("#dining-options-buttons button[data-value='both']")
        assert "ring-1" in both_btn.get_attribute("class")

        # Default rating is 5
        assert page.locator("#rating-stars").get_attribute("data-rating") == "5"

        # Close via X button
        page.locator("#close-modal-btn").click()
        assert modal.is_hidden()


# ---------------------------------------------------------------------------
# Add Restaurant Modal — Close on Outside Click
# ---------------------------------------------------------------------------


class TestAddModalOutsideClick:
    def test_close_on_outside_click(self, live_server, seed, page):
        seed()
        _goto(page, live_server)

        page.locator("#add-restaurant-btn").click()
        modal = page.locator("#restaurant-modal")
        assert modal.is_visible()

        # Click on the overlay (top-left corner of the modal overlay, outside the inner card)
        modal.click(position={"x": 5, "y": 5})
        assert modal.is_hidden()


# ---------------------------------------------------------------------------
# Edit Restaurant — View and Modify
# ---------------------------------------------------------------------------


class TestEditRestaurant:
    def test_view_and_modify(self, live_server, seed, page):
        seed(
            id="edit_r1",
            name="Taco Spot",
            diningOptions="delivery",
            rating=3,
            notes="Spicy food",
            dishes=[{"name": "Taco", "rating": 1}, {"name": "Burrito", "rating": 0}],
        )

        _goto(page, live_server)

        # Click card to open edit modal
        _click_card(page, "Taco Spot")
        modal = page.locator("#restaurant-modal")
        modal.wait_for(state="visible")

        # --- Verify pre-populated state ---
        assert page.locator("#modal-title").text_content().strip() == "Restaurant"
        assert page.locator("#edit-name-display").text_content().strip() == "Taco Spot"
        assert page.locator("#place-autocomplete").is_hidden()

        # Delivery button should be active
        delivery_btn = page.locator(
            "#dining-options-buttons button[data-value='delivery']"
        )
        assert "ring-1" in delivery_btn.get_attribute("class")

        # Rating is 3
        assert page.locator("#rating-stars").get_attribute("data-rating") == "3"

        # Notes
        assert page.locator("#restaurant-notes").input_value() == "Spicy food"

        # 2 dishes
        dishes_container = page.locator("#dishes-container")
        assert dishes_container.locator("> div").count() == 2

        # Refresh button visible
        assert page.locator("#refresh-restaurant-btn").is_visible()

        # Submit button
        submit = page.locator("#submit-btn")
        assert submit.text_content().strip() == "Save changes"
        assert submit.is_enabled()

        # --- Modify ---
        # Change type to dine-in
        page.locator("#dining-options-buttons button[data-value='dine-in']").click()

        # Change rating to 2 (click 2nd star, 0-indexed)
        stars = page.locator("#rating-stars svg")
        stars.nth(1).click()

        # Change notes
        notes_field = page.locator("#restaurant-notes")
        notes_field.fill("Updated notes")

        # Save
        submit.click()

        # Modal should close
        modal.wait_for(state="hidden")

        # Card should show dine-in icon badge
        page.locator("#list svg use[href='#icon-dine-in']").wait_for(state="visible")

        # Reopen modal to verify persisted values
        _click_card(page, "Taco Spot")
        modal.wait_for(state="visible")

        assert page.locator("#restaurant-notes").input_value() == "Updated notes"
        dine_in_btn = page.locator(
            "#dining-options-buttons button[data-value='dine-in']"
        )
        assert "ring-1" in dine_in_btn.get_attribute("class")
        assert page.locator("#rating-stars").get_attribute("data-rating") == "2"


# ---------------------------------------------------------------------------
# Delete Restaurant — Cancel and Confirm
# ---------------------------------------------------------------------------


class TestDeleteRestaurant:
    def test_cancel_then_confirm(self, live_server, seed, page):
        seed(id="del_r1", name="Delete Me")
        seed(id="del_r2", name="Keep Me")

        _goto(page, live_server)
        assert _card_locators(page).count() == 2

        # --- Cancel flow ---
        # Find the delete button on "Delete Me" card
        delete_me_card = page.locator(
            "#list .bg-white.rounded-lg", has=page.locator("text=Delete Me")
        )
        delete_me_card.locator("button[title='Delete']").click()

        delete_modal = page.locator("#delete-modal")
        assert delete_modal.is_visible()

        page.locator("#cancel-delete-btn").click()
        assert delete_modal.is_hidden()
        assert _card_locators(page).count() == 2

        # --- Confirm flow ---
        delete_me_card = page.locator(
            "#list .bg-white.rounded-lg", has=page.locator("text=Delete Me")
        )
        delete_me_card.locator("button[title='Delete']").click()
        delete_modal.wait_for(state="visible")

        page.locator("#confirm-delete-btn").click()
        delete_modal.wait_for(state="hidden")

        # Only 1 card should remain
        page.locator("span.text-lg.font-bold:has-text('Keep Me')").wait_for(
            state="visible"
        )
        assert _card_locators(page).count() == 1
        names = _card_names(page)
        assert "Keep Me" in names
        assert "Delete Me" not in names


# ---------------------------------------------------------------------------
# Filter — Search by Name
# ---------------------------------------------------------------------------


class TestFilterSearch:
    def test_search_by_name(self, live_server, seed, page):
        seed(id="s1", name="Burger Palace")
        seed(id="s2", name="Pasta House")
        seed(id="s3", name="Burger Barn", city="OtherCity")

        _goto(page, live_server)
        assert _card_locators(page).count() == 3

        # Search for "burger"
        page.locator("#search-input").fill("burger")
        page.wait_for_timeout(300)  # wait for input debounce / filter

        assert _card_locators(page).count() == 2
        names = _card_names(page)
        assert "Burger Palace" in names
        assert "Burger Barn" in names

        # Clear search
        page.locator("#search-input").fill("")
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 3


# ---------------------------------------------------------------------------
# Filter — By Type, City, Rating, Price + Clear Filters
# ---------------------------------------------------------------------------


class TestFilterDropdowns:
    def test_filter_combinations(self, live_server, seed, page):
        seed(
            id="f1",
            name="Dine One",
            diningOptions="dine-in",
            city="Amsterdam",
            rating=5,
            priceLevel=1,
        )
        seed(
            id="f2",
            name="Dine Two",
            diningOptions="dine-in",
            city="Zurich",
            rating=3,
            priceLevel=3,
        )
        seed(
            id="f3",
            name="Deliver One",
            diningOptions="delivery",
            city="Amsterdam",
            rating=4,
            priceLevel=2,
        )
        seed(
            id="f4",
            name="Both One",
            diningOptions="both",
            city="Zurich",
            rating=2,
            priceLevel=4,
        )

        _goto(page, live_server)
        assert _card_locators(page).count() == 4

        # Clear filters button should not be visible before any filter is applied
        assert not page.locator("#top-clear-filters-btn").is_visible()

        # Type: dine-in  (should match dine-in + both)
        _select_dropdown_option(page, "Dining Options", "dine-in")
        page.wait_for_timeout(300)
        names = _card_names(page)
        assert "Dine One" in names
        assert "Dine Two" in names
        assert "Both One" in names
        assert "Deliver One" not in names

        # Clear before next filter
        page.locator("#top-clear-filters-btn").click()
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 4

        # City: Amsterdam
        _select_dropdown_option(page, "City", "Amsterdam")
        page.wait_for_timeout(300)
        names = _card_names(page)
        assert "Dine One" in names
        assert "Deliver One" in names
        assert "Dine Two" not in names
        assert "Both One" not in names

        page.locator("#top-clear-filters-btn").click()
        page.wait_for_timeout(300)

        # Min Rating: 4
        _select_dropdown_option(page, "Rating", "4")
        page.wait_for_timeout(300)
        names = _card_names(page)
        assert "Dine One" in names
        assert "Deliver One" in names
        assert "Dine Two" not in names
        assert "Both One" not in names

        page.locator("#top-clear-filters-btn").click()
        page.wait_for_timeout(300)

        # Max Price: $$ (priceLevel <= 2)
        _select_dropdown_option(page, "Price", "2")
        page.wait_for_timeout(300)
        names = _card_names(page)
        assert "Dine One" in names
        assert "Deliver One" in names
        assert "Dine Two" not in names
        assert "Both One" not in names

        # Clear all
        page.locator("#top-clear-filters-btn").click()
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 4

    def test_cuisine_filter_populates_and_filters(self, live_server, seed, page):
        seed(id="c1", name="Sushi Spot", types=["japanese_restaurant"])
        seed(id="c2", name="Taco Place", types=["mexican_restaurant"])
        seed(
            id="c3",
            name="Noodle Bar",
            types=["japanese_restaurant", "chinese_restaurant"],
        )
        seed(id="c4", name="Plain Diner", types=[])

        _goto(page, live_server)
        assert _card_locators(page).count() == 4

        # Cuisine dropdown should contain Japanese, Chinese, Mexican (but not blank entries)
        _open_dropdown(page, "Cuisine")
        cuisine_options = page.locator("#cuisine-filter-options button")
        option_texts = [
            cuisine_options.nth(i).text_content().strip()
            for i in range(cuisine_options.count())
        ]
        assert "Japanese" in option_texts
        assert "Chinese" in option_texts
        assert "Mexican" in option_texts
        assert "" not in option_texts
        # Close the dropdown
        page.keyboard.press("Escape")

        # Filter by Japanese — should match Sushi Spot and Noodle Bar
        _select_dropdown_option(page, "Cuisine", "Japanese")
        page.wait_for_timeout(300)
        names = _card_names(page)
        assert "Sushi Spot" in names
        assert "Noodle Bar" in names
        assert "Taco Place" not in names
        assert "Plain Diner" not in names

        page.locator("#top-clear-filters-btn").click()
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 4

        # Filter by Mexican — should match only Taco Place
        _select_dropdown_option(page, "Cuisine", "Mexican")
        page.wait_for_timeout(300)
        names = _card_names(page)
        assert "Taco Place" in names
        assert "Sushi Spot" not in names
        assert "Noodle Bar" not in names
        assert "Plain Diner" not in names

    def test_cuisine_filter_updates_after_delete(self, live_server, seed, page):
        seed(id="d1", name="Only Japanese", types=["japanese_restaurant"])
        seed(id="d2", name="Burger Joint", types=["american_restaurant"])

        _goto(page, live_server)

        # Both cuisines should be present
        _open_dropdown(page, "Cuisine")
        option_texts = [
            page.locator("#cuisine-filter-options button").nth(i).text_content().strip()
            for i in range(page.locator("#cuisine-filter-options button").count())
        ]
        assert "Japanese" in option_texts
        assert "American" in option_texts

        # Delete the Japanese restaurant via API
        page.request.delete(
            f"{live_server}/api/restaurants/d1",
            headers={"X-CSRFToken": _csrf_token(page)},
        )

        # Reload page — Japanese cuisine should no longer appear
        _goto(page, live_server)
        _open_dropdown(page, "Cuisine")
        option_texts = [
            page.locator("#cuisine-filter-options button").nth(i).text_content().strip()
            for i in range(page.locator("#cuisine-filter-options button").count())
        ]
        assert "Japanese" not in option_texts
        assert "American" in option_texts


# ---------------------------------------------------------------------------
# No Matches — "Clear Filters" Button
# ---------------------------------------------------------------------------


class TestNoMatches:
    def test_no_matches_clear_filters(self, live_server, seed, page):
        seed(id="nm1", name="Lonely Restaurant")

        _goto(page, live_server)
        assert _card_locators(page).count() == 1

        page.locator("#search-input").fill("zzzzz")
        page.wait_for_timeout(300)

        assert page.locator("text=No matches found").is_visible()

        # Click the "Clear Filters" button inside the empty results area
        page.locator("#clear-filters-btn").click()
        page.wait_for_timeout(300)

        assert _card_locators(page).count() == 1
        assert "Lonely Restaurant" in _card_names(page)


# ---------------------------------------------------------------------------
# Dishes — Add Dish in Edit Modal
# ---------------------------------------------------------------------------


class TestDishAdd:
    def test_add_dish(self, live_server, seed, page):
        seed(id="dish_add_r1", name="Dish Test Place")

        _goto(page, live_server)

        # Open edit modal
        _click_card(page, "Dish Test Place")
        page.locator("#restaurant-modal").wait_for(state="visible")

        # No dishes yet
        assert page.locator("#dishes-container > div").count() == 0

        # Click "+ Add Dish"
        page.locator("#add-dish-btn").click()
        assert page.locator("#add-dish-form").is_visible()

        # Fill dish form
        page.locator("#new-dish-name").fill("Pad Thai")
        page.locator("#new-dish-notes").fill("Extra spicy")
        # Select thumbs-down (value=0)
        page.locator("input[name='new-dish-rating'][value='0']").check(force=True)

        # Save dish
        page.locator("#save-dish-btn").click()

        # Dish should appear in the list
        dishes = page.locator("#dishes-container > div")
        assert dishes.count() == 1
        assert page.locator("#dishes-container >> text=Pad Thai").is_visible()

        # Save the restaurant
        page.locator("#submit-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")

        # Reopen and verify persistence
        _click_card(page, "Dish Test Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert page.locator("#dishes-container > div").count() == 1
        assert page.locator("#dishes-container >> text=Pad Thai").is_visible()


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


# ---------------------------------------------------------------------------
# Dishes — Edit Dish Inline
# ---------------------------------------------------------------------------


class TestDishEdit:
    def test_edit_dish_inline(self, live_server, seed, page):
        seed(
            id="dish_edit_r1",
            name="Edit Dish Place",
            dishes=[{"name": "Fries", "rating": 1, "notes": "Crispy"}],
        )

        _goto(page, live_server)

        # Open edit modal
        _click_card(page, "Edit Dish Place")
        page.locator("#restaurant-modal").wait_for(state="visible")

        # Click edit button on the dish (pencil icon)
        dish_row = page.locator("#dishes-container > div").first
        dish_row.hover()
        dish_row.locator("button").first.click()  # edit button is first

        # Inline edit form should appear
        name_input = page.locator("#edit-dish-name-0")
        name_input.wait_for(state="visible")
        assert name_input.input_value() == "Fries"

        # Modify
        name_input.fill("Cheese Fries")
        # Flip to thumbs-down (value=0)
        page.locator("input[name='edit-rating-0'][value='0']").check(force=True)

        # Save inline edit
        page.locator("button:has-text('Save')").first.click()

        # Verify in dish list
        assert page.locator("#dishes-container >> text=Cheese Fries").is_visible()

        # Save restaurant
        page.locator("#submit-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")

        # Reopen and verify persistence
        _click_card(page, "Edit Dish Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert page.locator("#dishes-container >> text=Cheese Fries").is_visible()


# ---------------------------------------------------------------------------
# Dishes — Delete Dish
# ---------------------------------------------------------------------------


class TestDishDelete:
    def test_delete_dish(self, live_server, seed, page):
        seed(
            id="dish_del_r1",
            name="Del Dish Place",
            dishes=[{"name": "Wings", "rating": 1}, {"name": "Nachos", "rating": 0}],
        )

        _goto(page, live_server)

        _click_card(page, "Del Dish Place")
        page.locator("#restaurant-modal").wait_for(state="visible")

        assert page.locator("#dishes-container > div").count() == 2

        # Hover and click delete on first dish
        first_dish = page.locator("#dishes-container > div").first
        first_dish.hover()
        # Delete button is the second button (after edit)
        first_dish.locator("button").nth(1).click()

        assert page.locator("#dishes-container > div").count() == 1

        # Save
        page.locator("#submit-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")

        # Reopen and verify
        _click_card(page, "Del Dish Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert page.locator("#dishes-container > div").count() == 1


# ---------------------------------------------------------------------------
# Dishes — Cancel Add
# ---------------------------------------------------------------------------


class TestDishCancelAdd:
    def test_cancel_add_dish(self, live_server, seed, page):
        seed(id="dish_cancel_r1", name="Cancel Dish Place")

        _goto(page, live_server)

        _click_card(page, "Cancel Dish Place")
        page.locator("#restaurant-modal").wait_for(state="visible")

        initial_count = page.locator("#dishes-container > div").count()

        # Open add dish form
        page.locator("#add-dish-btn").click()
        assert page.locator("#add-dish-form").is_visible()

        # Type a name
        page.locator("#new-dish-name").fill("Phantom Dish")

        # Cancel
        page.locator("#cancel-dish-btn").click()

        # Form should be hidden, no new dish added
        assert page.locator("#add-dish-form").is_hidden()
        assert page.locator("#dishes-container > div").count() == initial_count


# ---------------------------------------------------------------------------
# Floating Action Button (FAB)
# ---------------------------------------------------------------------------


class TestFAB:
    """Tests for the mobile FAB (+) button.

    All tests set a mobile viewport (375px) so that the FAB is visible
    (it is hidden on sm+ screens via Tailwind's sm:hidden class).
    """

    MOBILE = {"width": 375, "height": 812}

    def test_fab_hidden_on_empty_state(self, live_server, page):
        """FAB should not be visible when there are no restaurants."""
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        assert page.locator("text=Nothing here yet").is_visible()
        assert page.locator("#add-restaurant-btn-fab").is_hidden()

    def test_fab_visible_with_restaurants(self, live_server, seed, page):
        """FAB should be visible once there is at least one restaurant card."""
        seed(id="fab_r1", name="FAB Visible Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        assert page.locator("#add-restaurant-btn-fab").is_visible()

    def test_fab_opens_modal_and_hides(self, live_server, seed, page):
        """Clicking the FAB opens the add-restaurant modal and hides the FAB."""
        seed(id="fab_r2", name="FAB Open Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        fab = page.locator("#add-restaurant-btn-fab")
        assert fab.is_visible()

        fab.click()
        modal = page.locator("#restaurant-modal")
        modal.wait_for(state="visible")
        assert page.locator("#modal-title").text_content().strip() == "Add Restaurant"
        assert fab.is_hidden()

    def test_fab_reappears_after_close(self, live_server, seed, page):
        """FAB reappears after the modal is closed via the X button."""
        seed(id="fab_r3", name="FAB Close Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        fab = page.locator("#add-restaurant-btn-fab")
        fab.click()
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert fab.is_hidden()

        page.locator("#close-modal-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")
        assert fab.is_visible()

    def test_fab_reappears_after_outside_click(self, live_server, seed, page):
        """FAB reappears when the modal overlay is dismissed by clicking outside."""
        seed(id="fab_r4", name="FAB Outside Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        fab = page.locator("#add-restaurant-btn-fab")
        fab.click()
        modal = page.locator("#restaurant-modal")
        modal.wait_for(state="visible")

        modal.click(position={"x": 5, "y": 5})
        modal.wait_for(state="hidden")
        assert fab.is_visible()

    def test_fab_hides_on_edit(self, live_server, seed, page):
        """FAB hides when the edit modal is opened by clicking a card."""
        seed(id="fab_r5", name="FAB Edit Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        fab = page.locator("#add-restaurant-btn-fab")
        assert fab.is_visible()

        _click_card(page, "FAB Edit Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert fab.is_hidden()

    def test_fab_reappears_after_save(self, live_server, seed, page):
        """FAB reappears after saving changes in the edit modal."""
        seed(id="fab_r6", name="FAB Save Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        fab = page.locator("#add-restaurant-btn-fab")
        _click_card(page, "FAB Save Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert fab.is_hidden()

        page.locator("#submit-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")
        assert fab.is_visible()

    def test_fab_hidden_when_switching_to_empty_pill_view(
        self, live_server, seed, page
    ):
        """FAB stays hidden when switching to a pill view that has no restaurants."""
        seed(id="fab_r7", name="FAB Have Been Place")
        page.set_viewport_size(self.MOBILE)
        _goto(page, live_server)

        # FAB is visible on "Have been" (has one restaurant)
        fab = page.locator("#add-restaurant-btn-fab")
        assert fab.is_visible()

        # Switch to "Want to go" — no wishlisted restaurants exist
        page.locator("#pill-want-to-go").click()
        assert page.locator("text=Nothing here yet").is_visible()
        assert fab.is_hidden()


# ---------------------------------------------------------------------------
# Sort
# ---------------------------------------------------------------------------


class TestSort:
    def _seed_three(self, seed):
        seed(id="so1", name="Zebra Grill", rating=5, priceLevel=1, city="Amsterdam")
        seed(id="so2", name="Apple Bistro", rating=3, priceLevel=3, city="Amsterdam")
        seed(id="so3", name="Mango House", rating=4, priceLevel=2, city="Zurich")

    def test_sort_by_name(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "Recently Added", "name")
        page.wait_for_timeout(300)
        assert page.locator(".sort-label").text_content().strip() == "Name"
        assert _card_names(page) == ["Apple Bistro", "Mango House", "Zebra Grill"]

    def test_sort_by_highest_rating(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "Recently Added", "rating")
        page.wait_for_timeout(300)
        assert page.locator(".sort-label").text_content().strip() == "Highest Rating"
        assert _card_names(page) == ["Zebra Grill", "Mango House", "Apple Bistro"]

    def test_sort_by_lowest_price(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "Recently Added", "price")
        page.wait_for_timeout(300)
        assert page.locator(".sort-label").text_content().strip() == "Lowest Price"
        assert _card_names(page) == ["Zebra Grill", "Mango House", "Apple Bistro"]

    def test_sort_preserved_when_filter_applied(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "Recently Added", "name")
        page.wait_for_timeout(300)
        _select_dropdown_option(page, "City", "Amsterdam")
        page.wait_for_timeout(300)
        assert _card_names(page) == ["Apple Bistro", "Zebra Grill"]

    def test_filter_preserved_when_sort_changed(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "City", "Amsterdam")
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 2
        _select_dropdown_option(page, "Recently Added", "rating")
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 2
        assert _card_names(page) == ["Zebra Grill", "Apple Bistro"]

    def test_clear_filters_preserves_sort(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "Recently Added", "name")
        page.wait_for_timeout(300)
        _select_dropdown_option(page, "City", "Amsterdam")
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 2
        page.locator("#top-clear-filters-btn").click()
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 3
        assert page.locator(".sort-label").text_content().strip() == "Name"
        assert _card_names(page) == ["Apple Bistro", "Mango House", "Zebra Grill"]

    def test_sort_preserved_after_delete(self, live_server, seed, page):
        self._seed_three(seed)
        _goto(page, live_server)
        _select_dropdown_option(page, "Recently Added", "name")
        page.wait_for_timeout(300)
        assert _card_names(page) == ["Apple Bistro", "Mango House", "Zebra Grill"]

        mango_card = page.locator(
            "#list .bg-white.rounded-lg", has=page.locator("text='Mango House'")
        )
        mango_card.locator("button[title='Delete']").click()
        page.locator("#delete-modal").wait_for(state="visible")
        page.locator("#confirm-delete-btn").click()
        page.locator("#delete-modal").wait_for(state="hidden")

        assert _card_locators(page).count() == 2
        assert page.locator(".sort-label").text_content().strip() == "Name"
        assert _card_names(page) == ["Apple Bistro", "Zebra Grill"]


# ---------------------------------------------------------------------------
# Wishlist Pills
# ---------------------------------------------------------------------------


class TestWishlistPills:
    def test_pill_toggle_filters_list(self, live_server, seed, page):
        seed(id="vis_r1", name="Already Visited")
        seed(id="wl_r1", name="Want To Go Place", wishlisted=True, rating=None)

        _goto(page, live_server)

        # Default "Visited" pill — only the visited restaurant
        assert _card_locators(page).count() == 1
        assert "Already Visited" in _card_names(page)

        # Add modal defaults to "Visited" while on Visited pill
        page.locator("#add-restaurant-btn").click()
        page.locator("#restaurant-modal").wait_for(state="visible")
        visited_btn = page.locator("#form-wishlist-buttons button[data-value='false']")
        assert "ring-1" in visited_btn.get_attribute("class")
        assert page.locator("#rating-section").is_visible()
        page.locator("#close-modal-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")

        # Switch to "Want to go" — only the wishlisted restaurant
        page.locator("#pill-want-to-go").click()
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 1
        assert "Want To Go Place" in _card_names(page)

        # Add modal defaults to "Want to go" while on Want to go pill
        page.locator("#add-restaurant-btn").click()
        page.locator("#restaurant-modal").wait_for(state="visible")
        want_to_go_btn = page.locator(
            "#form-wishlist-buttons button[data-value='true']"
        )
        assert "ring-1" in want_to_go_btn.get_attribute("class")
        assert page.locator("#rating-section").is_hidden()
        page.locator("#close-modal-btn").click()
        page.locator("#restaurant-modal").wait_for(state="hidden")

        # Switch back to "Visited"
        page.locator("#pill-visited").click()
        page.wait_for_timeout(300)
        assert _card_locators(page).count() == 1
        assert "Already Visited" in _card_names(page)

    def test_visited_pill_empty_state_and_add_modal_defaults(
        self, live_server, seed, page
    ):
        seed(id="wl_r1", name="Want To Go Place", wishlisted=True, rating=None)

        _goto(page, live_server)

        # "Visited" pill is active by default — no visited restaurants exist
        assert page.locator("text=Nothing here yet").is_visible()
        assert page.locator(
            "text=Get started by adding your first favorite dining spot."
        ).is_visible()

        # Open add modal from empty-state button
        page.locator("#empty-state-add-btn").click()
        page.locator("#restaurant-modal").wait_for(state="visible")

        # Toggle should default to "Visited" (formWishlisted = false → Visited button active)
        visited_btn = page.locator("#form-wishlist-buttons button[data-value='false']")
        assert "ring-1" in visited_btn.get_attribute("class")

        # Rating section should be visible
        assert page.locator("#rating-section").is_visible()

    def test_want_to_go_pill_empty_state_and_add_modal_defaults(
        self, live_server, seed, page
    ):
        seed(id="vis_r1", name="Already Visited")

        _goto(page, live_server)

        # Switch to "Want to go" — no wishlisted restaurants exist
        page.locator("#pill-want-to-go").click()
        page.wait_for_timeout(300)

        assert page.locator("text=Nothing here yet").is_visible()
        assert page.locator(
            "text=Is there a restaurant you would like to visit?"
        ).is_visible()

        # Open add modal from empty-state button
        page.locator("#empty-state-add-btn").click()
        page.locator("#restaurant-modal").wait_for(state="visible")

        # Toggle should default to "Want to go" (formWishlisted = true → Want to go button active)
        want_to_go_btn = page.locator(
            "#form-wishlist-buttons button[data-value='true']"
        )
        assert "ring-1" in want_to_go_btn.get_attribute("class")

        # Rating section should be hidden
        assert page.locator("#rating-section").is_hidden()

    def test_mark_as_visited_from_card(self, live_server, seed, page):
        seed(id="wl_r1", name="Want To Go Place", wishlisted=True, rating=None)

        _goto(page, live_server)

        # Switch to "Want to go" to see the wishlisted card
        page.locator("#pill-want-to-go").click()
        page.wait_for_timeout(300)
        assert "Want To Go Place" in _card_names(page)

        # Click the greyed-out stars to open the mark-as-visited modal
        page.locator("[title='Mark as visited']").click()
        mark_visited_modal = page.locator("#mark-visited-modal")
        mark_visited_modal.wait_for(state="visible")

        # Pick 3 stars (0-indexed: click the 3rd star)
        page.locator("#mark-visited-stars svg").nth(2).click()
        assert page.locator("#mark-visited-stars").get_attribute("data-rating") == "3"

        page.locator("#confirm-mark-visited-btn").click()
        mark_visited_modal.wait_for(state="hidden")

        # Card should disappear from "Want to go" view — empty state shown
        page.locator("text=Nothing here yet").wait_for(state="visible")

        # Switch to "Visited" — card should now appear with correct rating
        page.locator("#pill-visited").click()
        page.wait_for_timeout(300)
        assert "Want To Go Place" in _card_names(page)

        # Open edit modal and verify rating was saved
        _click_card(page, "Want To Go Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert page.locator("#rating-stars").get_attribute("data-rating") == "3"

    def test_mark_as_visited_from_edit_modal(self, live_server, seed, page):
        seed(id="wl_r1", name="Want To Go Place", wishlisted=True, rating=None)

        _goto(page, live_server)

        # Switch to "Want to go"
        page.locator("#pill-want-to-go").click()
        page.wait_for_timeout(300)

        # Open edit modal
        _click_card(page, "Want To Go Place")
        modal = page.locator("#restaurant-modal")
        modal.wait_for(state="visible")

        # "Mark as visited" button should be visible in edit modal
        page.locator("#modal-mark-visited-btn").wait_for(state="visible")
        page.locator("#modal-mark-visited-btn").click()

        mark_visited_modal = page.locator("#mark-visited-modal")
        mark_visited_modal.wait_for(state="visible")

        # Pick 4 stars (0-indexed: click the 4th star)
        page.locator("#mark-visited-stars svg").nth(3).click()
        assert page.locator("#mark-visited-stars").get_attribute("data-rating") == "4"

        page.locator("#confirm-mark-visited-btn").click()
        mark_visited_modal.wait_for(state="hidden")

        # Edit modal should also close
        modal.wait_for(state="hidden")

        # Restaurant now in "Visited" view with rating 4
        page.locator("#pill-visited").click()
        page.wait_for_timeout(300)
        assert "Want To Go Place" in _card_names(page)

        # Open edit modal and verify rating was saved
        _click_card(page, "Want To Go Place")
        page.locator("#restaurant-modal").wait_for(state="visible")
        assert page.locator("#rating-stars").get_attribute("data-rating") == "4"

    def test_wishlist_toggle_shows_hides_rating_stars(self, live_server, seed, page):
        seed(id="vis_r1", name="Visited Place")

        _goto(page, live_server)

        # Open add modal (from "Visited" pill — default)
        page.locator("#add-restaurant-btn").click()
        page.locator("#restaurant-modal").wait_for(state="visible")

        # Default: "Visited" toggle active, rating section visible
        visited_btn = page.locator("#form-wishlist-buttons button[data-value='false']")
        assert "ring-1" in visited_btn.get_attribute("class")
        assert page.locator("#rating-section").is_visible()

        # Switch to "Want to go" — rating section should hide
        page.locator("#form-wishlist-buttons button[data-value='true']").click()
        assert page.locator("#rating-section").is_hidden()

        # Switch back to "Visited" — rating section should reappear
        page.locator("#form-wishlist-buttons button[data-value='false']").click()
        assert page.locator("#rating-section").is_visible()

    def test_rating_filter_hidden_on_want_to_go_pill(self, live_server, seed, page):
        seed(id="vis_r1", name="Visited Place", rating=4)
        seed(id="wl_r1", name="Want To Go Place", wishlisted=True, rating=None)

        _goto(page, live_server)

        # Default: "Visited" pill active — rating filter should be visible
        assert page.locator("#rating-filter-container").is_visible()

        # Select a rating filter
        _select_dropdown_option(page, "Rating", "4")
        page.wait_for_timeout(300)
        assert page.locator("#top-clear-filters-btn").is_visible()

        # Switch to "Want to go" — rating filter should be hidden
        page.locator("#pill-want-to-go").click()
        page.wait_for_timeout(300)
        assert page.locator("#rating-filter-container").is_hidden()

        # Switch back to "Visited" — rating filter reappears with selection intact
        page.locator("#pill-visited").click()
        page.wait_for_timeout(300)
        assert page.locator("#rating-filter-container").is_visible()
        rating_label = page.locator(
            "#rating-filter-container .dropdown-trigger .filter-label"
        )
        assert "4" in rating_label.text_content()
        assert page.locator("#top-clear-filters-btn").is_visible()

    def test_highest_rating_sort_hidden_on_want_to_go_pill(
        self, live_server, seed, page
    ):
        seed(id="vis_r1", name="Visited Place", rating=4)
        seed(id="wl_r1", name="Want To Go Place", wishlisted=True, rating=None)

        _goto(page, live_server)

        # Default: "Visited" pill — Highest Rating sort option should be present
        _open_dropdown(page, "Recently Added")
        assert page.locator(".sort-dropdown [data-value='rating']").is_visible()

        # Select "Highest Rating" sort
        page.locator(".sort-dropdown [data-value='rating']").click()
        page.wait_for_timeout(300)
        sort_label = page.locator(".sort-dropdown .sort-label")
        assert sort_label.text_content().strip() == "Highest Rating"

        # Switch to "Want to go" — Highest Rating option should be hidden and sort reset
        page.locator("#pill-want-to-go").click()
        page.wait_for_timeout(300)
        assert page.locator(".sort-dropdown [data-value='rating']").is_hidden()
        assert sort_label.text_content().strip() == "Recently Added"

        # Switch back to "Visited" — Highest Rating option reappears (open dropdown to confirm)
        page.locator("#pill-visited").click()
        page.wait_for_timeout(300)
        _open_dropdown(page, "Recently Added")
        assert page.locator(".sort-dropdown [data-value='rating']").is_visible()
