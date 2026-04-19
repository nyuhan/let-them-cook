"""
UI tests for empty state and card rendering.
"""

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
