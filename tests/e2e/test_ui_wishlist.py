"""
UI tests for wishlist pill toggling and mark-as-visited flows.
"""

from tests.e2e.utils import (
    _card_locators,
    _card_names,
    _click_card,
    _csrf_token,
    _goto,
    _open_dropdown,
    _select_dropdown_option,
)


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
