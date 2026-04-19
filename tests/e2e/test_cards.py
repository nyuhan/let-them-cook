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

        # Share button should be visible on each card
        cards = _card_locators(page)
        for i in range(cards.count()):
            card = cards.nth(i)
            assert card.locator("a[title='Open in Google Maps']").is_visible()
            assert card.locator("a[title='Navigate']").is_visible()
            assert card.locator("button[title='Share']").is_visible()
            assert card.locator("button[title='Delete']").is_visible()

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
# Share Button
# ---------------------------------------------------------------------------

_SHARE_RESTAURANT = "Share Test Place"
# Must match the default mapUri in the seed fixture
_SHARE_MAP_URI = "https://maps.example.com/place"

# CSS attribute selectors used to detect which icon is rendered inside the button
_CHECKMARK_PATH = "path[d^='M5 13']"  # checkmark: d="M5 13l4 4L19 7"
_SHARE_ICON_PATH = "path[d^='M18 16']"  # share icon: d="M18 16.08c…"


def _share_btn(page, name=_SHARE_RESTAURANT):
    card = page.locator("#list .bg-white.rounded-lg", has=page.locator(f"text={name}"))
    return card.locator("button[title='Share']")


class TestShareButton:
    # -----------------------------------------------------------------------
    # navigator.share path
    # -----------------------------------------------------------------------

    def test_native_share_args_and_no_checkmark(self, live_server, seed, page):
        page.add_init_script(
            """
            window._shareArgs = null;
            navigator.share = (data) => { window._shareArgs = data; return Promise.resolve(); };
        """
        )
        seed(id="sb1", name=_SHARE_RESTAURANT)
        _goto(page, live_server)

        btn = _share_btn(page)
        btn.click()
        page.wait_for_function("window._shareArgs !== null")

        args = page.evaluate("window._shareArgs")
        assert args["url"] == _SHARE_MAP_URI
        assert args["title"] == _SHARE_RESTAURANT

        # Successful native share must not show the copy checkmark
        assert btn.locator(_CHECKMARK_PATH).count() == 0

    # -----------------------------------------------------------------------
    # Clipboard fallback (navigator.share absent)
    # -----------------------------------------------------------------------

    def test_clipboard_copy_url_checkmark_and_revert(self, live_server, seed, page):
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
            window._copied = null;
            Object.defineProperty(navigator, 'clipboard', {
                value: { writeText: (t) => { window._copied = t; return Promise.resolve(); } },
                configurable: true
            });
        """
        )
        seed(id="sb5", name=_SHARE_RESTAURANT)
        _goto(page, live_server)

        btn = _share_btn(page)
        btn.click()

        page.wait_for_function("window._copied !== null")
        assert page.evaluate("window._copied") == _SHARE_MAP_URI

        btn.locator(_CHECKMARK_PATH).wait_for(state="visible")

        page.wait_for_timeout(2200)

        # Checkmark should disappear after 2 seconds, reverting back to share icon
        assert btn.locator(_CHECKMARK_PATH).count() == 0
        assert btn.locator(_SHARE_ICON_PATH).is_visible()

    # -----------------------------------------------------------------------
    # execCommand fallback (clipboard unavailable)
    # -----------------------------------------------------------------------

    def test_exec_command_copy_and_checkmark(self, live_server, seed, page):
        page.add_init_script(
            """
            Object.defineProperty(navigator, 'share', { value: undefined, configurable: true });
            Object.defineProperty(navigator, 'clipboard', {
                value: { writeText: () => Promise.reject(new Error('not allowed')) },
                configurable: true
            });
            window._execCopied = false;
            const _origExec = document.execCommand.bind(document);
            document.execCommand = (cmd, ...args) => {
                if (cmd === 'copy') window._execCopied = true;
                try { return _origExec(cmd, ...args); } catch (_) { return false; }
            };
        """
        )
        seed(id="sb8", name=_SHARE_RESTAURANT)
        _goto(page, live_server)

        btn = _share_btn(page)
        btn.click()

        page.wait_for_function("window._execCopied === true")
        assert page.evaluate("window._execCopied") is True

        btn.locator(_CHECKMARK_PATH).wait_for(state="visible")

        page.wait_for_timeout(2200)

        # Checkmark should disappear after 2 seconds, reverting back to share icon
        assert btn.locator(_CHECKMARK_PATH).count() == 0
        assert btn.locator(_SHARE_ICON_PATH).is_visible()
