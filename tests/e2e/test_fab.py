"""
UI tests for the mobile floating action button (FAB).
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
