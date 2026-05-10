"""
UI tests for the add/edit modal, delete modal, and autocomplete clearing.
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

        # Default state: all 3 pills are pre-selected
        dine_in_btn = page.locator("#dining-options-buttons button[data-value='dine-in']")
        assert "bg-indigo-50" in dine_in_btn.get_attribute("class")

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
            diningOptions=["delivery"],
            rating=3,
            notes="Spicy food",
            address="123 Main St",
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

        # Address section should be visible and show the address
        address_container = page.locator("#address-container")
        assert address_container.is_visible()
        assert "123 Main St" in address_container.text_content()

        # Delivery button should be active
        delivery_btn = page.locator(
            "#dining-options-buttons button[data-value='delivery']"
        )
        assert "bg-indigo-50" in delivery_btn.get_attribute("class")

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
        assert "bg-indigo-50" in dine_in_btn.get_attribute("class")
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
# Autocomplete Clearing — input event and X-button click
# ---------------------------------------------------------------------------


class TestAutocompleteClearing:
    def _open_modal_with_visible_sections(self, live_server, seed, page):
        """Open the add modal and inject visible address + opening-hours state."""
        seed()
        _goto(page, live_server)
        page.locator("#add-restaurant-btn").click()
        page.locator("#restaurant-modal").wait_for(state="visible")
        # Enable submit button and show both sections via JS
        page.evaluate(
            """() => {
            displayAddress('99 Test Ave');
            document.getElementById('opening-hours-container').classList.remove('hidden');
            const btn = document.getElementById('submit-btn');
            btn.disabled = false;
            btn.classList.remove('opacity-50', 'cursor-not-allowed');
        }"""
        )
        assert page.locator("#address-container").is_visible()
        assert page.locator("#opening-hours-container").is_visible()
        assert page.locator("#submit-btn").is_enabled()

    def test_input_event_clears_sections_and_disables_submit(
        self, live_server, seed, page
    ):
        self._open_modal_with_visible_sections(live_server, seed, page)

        # Act: fire the input event
        page.evaluate(
            """() => {
            const el = document.getElementById('place-autocomplete');
            el.dispatchEvent(new Event('input', { bubbles: true }));
        }"""
        )

        # Assert: all three reset
        assert page.locator("#address-container").is_hidden()
        assert page.locator("#opening-hours-container").is_hidden()
        assert page.locator("#submit-btn").is_disabled()

    def test_clear_click_clears_sections_and_disables_submit(
        self, live_server, seed, page
    ):
        self._open_modal_with_visible_sections(live_server, seed, page)

        # Act: simulate X-button click — empty the value then dispatch click
        page.evaluate(
            """() => {
            const el = document.getElementById('place-autocomplete');
            el.value = '';
            el.dispatchEvent(new Event('click', { bubbles: true }));
        }"""
        )
        # The handler uses setTimeout(..., 0) — wait for the microtask to flush
        page.wait_for_timeout(50)

        # Assert: all three reset
        assert page.locator("#address-container").is_hidden()
        assert page.locator("#opening-hours-container").is_hidden()
        assert page.locator("#submit-btn").is_disabled()
