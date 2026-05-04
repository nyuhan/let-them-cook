"""
UI tests for map view: toggle, empty state, markers, and card panel.

These tests inject a mock Google Maps JS API (blocking the CDN) so they run
offline without a real API key.  MAP_ID must be present in the template for
the toggle buttons and map container to render; the ``map_live_server``
fixture sets that env-var for each test that needs it.
"""

import pytest

from tests.e2e.utils import _goto

# ---------------------------------------------------------------------------
# Mock Google Maps JS — injected via add_init_script before page load
# ---------------------------------------------------------------------------

_GOOGLE_MAPS_MOCK_JS = """
(function () {
  var _markers = [];

  function MockMap(container, opts) {
    this._listeners = {};
    // controls[ControlPosition.RIGHT_TOP] (index 3) must have .push()
    this.controls = Array.from({ length: 10 }, function () {
      return { push: function () {} };
    });
    window._mockMapInstance = this;
  }
  MockMap.prototype.addListener = function (event, fn) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(fn);
    return { remove: function () {} };
  };
  MockMap.prototype.setCenter = function () {};
  MockMap.prototype.setZoom = function () {};
  MockMap.prototype.fitBounds = function () {};
  MockMap.prototype._trigger = function (event) {
    var fns = this._listeners[event] || [];
    for (var i = 0; i < fns.length; i++) fns[i]();
  };

  function MockLatLngBounds() {}
  MockLatLngBounds.prototype.extend = function () {};
  MockLatLngBounds.prototype.getCenter = function () {
    return { lat: 0, lng: 0 };
  };

  function MockAdvancedMarkerElement(opts) {
    this._listeners = {};
    this._map = (opts && opts.map) || null;
    this.position = (opts && opts.position) || null;
    this.title = (opts && opts.title) || "";
    this.content = (opts && opts.content) || null;
    _markers.push(this);
  }
  Object.defineProperty(MockAdvancedMarkerElement.prototype, "map", {
    get: function () { return this._map; },
    set: function (val) { this._map = val; },
  });
  MockAdvancedMarkerElement.prototype.addListener = function (event, fn) {
    if (!this._listeners[event]) this._listeners[event] = [];
    this._listeners[event].push(fn);
    return { remove: function () {} };
  };
  MockAdvancedMarkerElement.prototype._trigger = function (event) {
    var fns = this._listeners[event] || [];
    for (var i = 0; i < fns.length; i++) fns[i]();
  };

  window.google = {
    maps: {
      Map: MockMap,
      LatLngBounds: MockLatLngBounds,
      CollisionBehavior: {
        OPTIONAL_AND_HIDES_LOWER_PRIORITY: "OPTIONAL_AND_HIDES_LOWER_PRIORITY",
      },
      ControlPosition: { RIGHT_TOP: 3 },
      marker: { AdvancedMarkerElement: MockAdvancedMarkerElement },
    },
  };
  window._mockMapMarkers = _markers;
})();
"""

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def map_live_server(live_server, monkeypatch):
    """Live server with MAP_ID set so the toggle buttons and map container render."""
    monkeypatch.setenv("MAP_ID", "test-map-id-for-e2e")
    yield live_server


@pytest.fixture()
def maps_page(context):
    """Authenticated page with Google Maps API mocked and CDN requests aborted."""
    p = context.new_page()
    p.set_default_timeout(10000)
    p.route("**/maps.googleapis.com/**", lambda route: route.abort())
    p.add_init_script(_GOOGLE_MAPS_MOCK_JS)
    yield p
    p.close()


def _switch_to_map(page):
    """Click the map toggle button and wait for the map view to become visible."""
    page.locator("#view-map-btn").click()
    page.locator("#map-view").wait_for(state="visible")


# ---------------------------------------------------------------------------
# Toggle tests  (DOM-only; no Google Maps rendering needed)
# ---------------------------------------------------------------------------


class TestMapToggle:
    def test_toggle_buttons_absent_without_map_id(self, live_server, page, monkeypatch):
        """Without MAP_ID the view-toggle buttons are not present in the DOM."""
        monkeypatch.delenv("MAP_ID", raising=False)
        _goto(page, live_server)
        assert not page.locator("#view-map-btn").is_visible()
        assert not page.locator("#view-list-btn").is_visible()

    def test_list_view_active_by_default(self, map_live_server, maps_page):
        """With MAP_ID, list view is shown and its button has the active style."""
        _goto(maps_page, map_live_server)
        assert maps_page.locator("#list").is_visible()
        assert not maps_page.locator("#map-view").is_visible()
        assert "bg-indigo-50" in maps_page.locator("#view-list-btn").get_attribute(
            "class"
        )

    def test_toggle_to_map_view(self, map_live_server, maps_page):
        """Clicking the map button hides the list and shows the map view."""
        _goto(maps_page, map_live_server)
        maps_page.locator("#view-map-btn").click()
        maps_page.locator("#map-view").wait_for(state="visible")
        assert not maps_page.locator("#list").is_visible()
        assert "bg-indigo-50" in maps_page.locator("#view-map-btn").get_attribute(
            "class"
        )

    def test_toggle_back_to_list(self, map_live_server, maps_page):
        """After switching to map, the list button restores the list view."""
        _goto(maps_page, map_live_server)
        maps_page.locator("#view-map-btn").click()
        maps_page.locator("#map-view").wait_for(state="visible")
        maps_page.locator("#view-list-btn").click()
        maps_page.locator("#list").wait_for(state="visible")
        assert not maps_page.locator("#map-view").is_visible()


# ---------------------------------------------------------------------------
# Empty-state overlay tests
# ---------------------------------------------------------------------------


class TestMapEmptyState:
    def test_empty_state_no_restaurants(self, map_live_server, maps_page):
        """With no restaurants the map shows the 'No restaurants added yet' overlay."""
        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)
        overlay = maps_page.locator(".map-empty-overlay")
        overlay.wait_for(state="visible")
        assert "No restaurants added yet" in overlay.text_content()

    def test_empty_state_no_coords(self, map_live_server, seed, maps_page):
        """Restaurants without coordinates show the 'No matches found' overlay."""
        seed(id="r1", name="No-Coord Bistro")  # default seed has no lat/lng
        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)
        overlay = maps_page.locator(".map-empty-overlay")
        overlay.wait_for(state="visible")
        assert "No matches found" in overlay.text_content()


# ---------------------------------------------------------------------------
# Marker rendering tests
# ---------------------------------------------------------------------------


class TestMapMarkers:
    def test_markers_rendered_for_restaurants_with_coords(
        self, map_live_server, seed, maps_page
    ):
        """Only restaurants that have coordinates get a map marker."""
        seed(id="r1", name="With Coords", latitude=48.8566, longitude=2.3522)
        seed(id="r2", name="No Coords Café")

        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)

        # Active markers are those whose _map was not cleared (not null)
        titles = maps_page.evaluate(
            "window._mockMapMarkers.filter(m => m._map !== null).map(m => m.title)"
        )
        assert "With Coords" in titles
        assert "No Coords Café" not in titles

    def test_search_filter_limits_map_markers(self, map_live_server, seed, maps_page):
        """When a search filter is active only matching restaurants get markers."""
        seed(id="r1", name="Sushi Place", latitude=35.6762, longitude=139.6503)
        seed(id="r2", name="Pizza House", latitude=41.9028, longitude=12.4964)

        _goto(maps_page, map_live_server)

        # Apply filter while still in list view so renderMap picks it up on switch
        maps_page.locator("#search-input").fill("sushi")
        maps_page.wait_for_timeout(300)

        _switch_to_map(maps_page)

        titles = maps_page.evaluate(
            "window._mockMapMarkers.filter(m => m._map !== null).map(m => m.title)"
        )
        assert "Sushi Place" in titles
        assert "Pizza House" not in titles


# ---------------------------------------------------------------------------
# Card-panel tests
# ---------------------------------------------------------------------------


class TestMapCardPanel:
    def test_marker_click_shows_card_panel(self, map_live_server, seed, maps_page):
        """Clicking a marker opens the card panel showing the restaurant's name."""
        seed(id="r1", name="Grand Café", latitude=48.8566, longitude=2.3522)

        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)

        maps_page.evaluate("window._mockMapMarkers[0]._trigger('click')")

        panel = maps_page.locator("#map-card-panel")
        panel.wait_for(state="visible")
        assert "Grand Café" in panel.text_content()

    def test_map_click_dismisses_card_panel(self, map_live_server, seed, maps_page):
        """Clicking the map background closes the open card panel."""
        seed(id="r1", name="Grand Café", latitude=48.8566, longitude=2.3522)

        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)

        maps_page.evaluate("window._mockMapMarkers[0]._trigger('click')")
        maps_page.locator("#map-card-panel").wait_for(state="visible")

        maps_page.evaluate("window._mockMapInstance._trigger('click')")

        maps_page.locator("#map-card-panel").wait_for(state="hidden")

    def test_card_panel_is_compact_no_notes_or_dishes(
        self, map_live_server, seed, maps_page
    ):
        """The map card panel (compact mode) omits notes and dishes sections."""
        seed(
            id="r1",
            name="Tasty Spot",
            latitude=51.5074,
            longitude=-0.1278,
            notes="Secret recipe inside",
            dishes=[{"name": "Steak Frites", "rating": 1}],
        )

        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)

        maps_page.evaluate("window._mockMapMarkers[0]._trigger('click')")
        panel = maps_page.locator("#map-card-panel")
        panel.wait_for(state="visible")

        panel_text = panel.text_content()
        assert "Tasty Spot" in panel_text
        assert "Secret recipe inside" not in panel_text
        assert "Steak Frites" not in panel_text

    def test_card_panel_click_opens_edit_modal(self, map_live_server, seed, maps_page):
        """Clicking the card panel card opens the edit modal for that restaurant."""
        seed(id="r1", name="Edit Me", latitude=48.8566, longitude=2.3522)

        _goto(maps_page, map_live_server)
        _switch_to_map(maps_page)

        maps_page.evaluate("window._mockMapMarkers[0]._trigger('click')")
        maps_page.locator("#map-card-panel").wait_for(state="visible")

        # Click the card inside the panel (the .bg-white div that renderCard creates)
        maps_page.locator("#map-card-panel .bg-white").first.click()

        modal = maps_page.locator("#restaurant-modal")
        modal.wait_for(state="visible")
        # enterEditMode sets modal-title to "Restaurant"
        assert maps_page.locator("#modal-title").text_content().strip() == "Restaurant"
