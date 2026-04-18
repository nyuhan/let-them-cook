"""Shared Playwright page helpers for e2e tests."""


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
