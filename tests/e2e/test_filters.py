"""
UI tests for search, dropdown filters, and no-matches state.
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
            diningOptions=["dine-in"],
            city="Amsterdam",
            rating=5,
            priceLevel=1,
        )
        seed(
            id="f2",
            name="Dine Two",
            diningOptions=["dine-in"],
            city="Zurich",
            rating=3,
            priceLevel=3,
        )
        seed(
            id="f3",
            name="Deliver One",
            diningOptions=["delivery"],
            city="Amsterdam",
            rating=4,
            priceLevel=2,
        )
        seed(
            id="f4",
            name="Both One",
            diningOptions=["dine-in", "delivery"],
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
