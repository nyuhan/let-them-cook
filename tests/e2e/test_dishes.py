"""
UI tests for dish CRUD within the edit modal.
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
