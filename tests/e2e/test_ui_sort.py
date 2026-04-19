"""
UI tests for sort functionality.
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
