"""
Tests for POST /api/restaurants.
"""

import json
import sqlite3
import app as app_module
from app import snake_to_camel


# ---------------------------------------------------------------------------
# POST /api/restaurants
# ---------------------------------------------------------------------------


class TestCreateRestaurant:
    def test_success(self, client, seed_restaurant):
        data, resp = seed_restaurant()
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["name"] == "Test Restaurant"
        assert body["id"] == data["id"]
        assert body["address"] == "123 Main St"
        assert body["city"] == "TestCity"
        assert body["mapUri"] == "https://maps.example.com/place"
        assert body["directionsUri"] == "https://maps.example.com/dir"
        assert body["diningOptions"] == ["dine-in"]
        assert body["priceLevel"] == 2
        assert body["notes"] == "Great place"
        assert body["types"] == ["restaurant"]
        assert body["cuisines"] == []
        assert body["openingHours"] is None
        assert body["dishes"] == []
        assert body["wishlisted"] is False
        assert body["rating"] == 4
        assert body["latitude"] == 48.8566
        assert body["longitude"] == 2.3522
        assert "createdAt" in body

    def test_with_dishes(self, client, seed_restaurant):
        dishes = [
            {"name": "Pizza", "rating": 1, "notes": "good"},
            {"name": "Pasta", "rating": 0, "notes": "meh"},
        ]
        data, resp = seed_restaurant(dishes=dishes)
        assert resp.status_code == 201
        assert len(resp.get_json()["dishes"]) == 2

    def test_restaurant_notes_normalised_to_null(self, client, seed_restaurant):
        """Empty string and explicit null notes both produce null on the restaurant."""
        _, resp = seed_restaurant(notes="")
        assert resp.status_code == 201
        assert resp.get_json()["notes"] is None

        _, resp = seed_restaurant(id="r2", notes=None)
        assert resp.status_code == 201
        assert resp.get_json()["notes"] is None

    def test_dish_notes_normalised_to_null(self, client, seed_restaurant):
        """Empty string, explicit null, and omitted notes all produce null."""
        dishes = [
            {"name": "A", "rating": 1, "notes": ""},
            {"name": "B", "rating": 1, "notes": None},
            {"name": "C", "rating": 1},
        ]
        data, resp = seed_restaurant(dishes=dishes)
        assert resp.status_code == 201
        assert all(d["notes"] is None for d in resp.get_json()["dishes"])

    def test_with_opening_hours(self, client, seed_restaurant):
        hours = {"weekdayDescriptions": ["Monday: 9 AM – 5 PM"], "periods": []}
        data, resp = seed_restaurant(openingHours=hours)
        assert resp.status_code == 201
        assert resp.get_json()["openingHours"] == hours

    def test_with_types(self, client, seed_restaurant):
        types = ["restaurant", "food", "italian_restaurant"]
        data, resp = seed_restaurant(types=types)
        assert resp.status_code == 201
        assert resp.get_json()["types"] == types

    def test_types_default_empty(self, client, seed_restaurant):
        data, resp = seed_restaurant(types=None)
        assert resp.status_code == 201
        assert resp.get_json()["types"] == []

    def test_invalid_rating_string(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "R",
                "diningOptions": ["dine-in"],
                "rating": "bad",
                "address": "a",
                "city": "c",
            },
        )
        assert resp.status_code == 400
        assert "rating" in resp.get_json()["error"].lower()

    def test_rating_out_of_range(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "R",
                "diningOptions": ["dine-in"],
                "rating": 6,
                "address": "a",
                "city": "c",
            },
        )
        assert resp.status_code == 400

    def test_rating_zero(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "R",
                "diningOptions": ["dine-in"],
                "rating": 0,
                "address": "a",
                "city": "c",
            },
        )
        assert resp.status_code == 400

    def test_invalid_type(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "R",
                "diningOptions": ["takeaway"],
                "rating": 3,
                "address": "a",
                "city": "c",
            },
        )
        assert resp.status_code == 400

    def test_dining_options_omitted_defaults_to_empty(self, client):
        """Omitting diningOptions entirely defaults to an empty list."""
        resp = client.post(
            "/api/restaurants",
            json={"id": "x", "name": "R", "rating": 3, "address": "a", "city": "c"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["diningOptions"] == []

    def test_dining_options_null_rejected(self, client):
        """Explicitly sending null is rejected."""
        resp = client.post(
            "/api/restaurants",
            json={"id": "x", "name": "R", "diningOptions": None, "rating": 3, "address": "a", "city": "c"},
        )
        assert resp.status_code == 400

    def test_dining_options_multiple_values(self, client, seed_restaurant):
        """Multiple valid values round-trip correctly."""
        _, resp = seed_restaurant(diningOptions=["dine-in", "delivery", "takeout"])
        assert resp.status_code == 201
        assert resp.get_json()["diningOptions"] == ["dine-in", "delivery", "takeout"]

    def test_missing_name(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "",
                "diningOptions": ["dine-in"],
                "rating": 3,
                "address": "a",
                "city": "c",
            },
        )
        assert resp.status_code == 400

    def test_duplicate_dish_name_rejected(self, client, seed_restaurant):
        dishes = [
            {"name": "Pizza", "rating": 1},
            {"name": "Pizza", "rating": 0},
        ]
        _, resp = seed_restaurant(dishes=dishes)
        assert resp.status_code == 400
        assert "Duplicate dish: Pizza" in resp.get_json()["error"]

    def test_dish_with_invalid_rating_skipped(self, client, seed_restaurant):
        dishes = [
            {"name": "Good", "rating": 1},
            {"name": "Bad", "rating": "nope"},
            {"name": "OutOfRange", "rating": 5},
        ]
        data, resp = seed_restaurant(dishes=dishes)
        assert resp.status_code == 201
        body = resp.get_json()
        # Only "Good" should have been inserted
        assert len(body["dishes"]) == 1
        assert body["dishes"][0]["name"] == "Good"

    def test_wishlisted_no_rating(self, client, seed_restaurant):
        _, resp = seed_restaurant(wishlisted=True, rating=None)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["wishlisted"] is True
        assert body["rating"] is None

    def test_wishlisted_explicit_false(self, client, seed_restaurant):
        _, resp = seed_restaurant(wishlisted=False, rating=3)
        assert resp.status_code == 201
        body = resp.get_json()
        assert body["wishlisted"] is False
        assert body["rating"] == 3

    def test_wishlisted_and_rating_both_set_rejected(self, client, seed_restaurant):
        _, resp = seed_restaurant(wishlisted=True, rating=4)
        assert resp.status_code == 400
        assert "exactly one" in resp.get_json()["error"]

    def test_no_rating_and_not_wishlisted_rejected(self, client, seed_restaurant):
        # Explicit False + no rating
        _, resp = seed_restaurant(wishlisted=False, rating=None)
        assert resp.status_code == 400
        assert "exactly one" in resp.get_json()["error"]
        # Neither field provided (wishlisted defaults False)
        resp2 = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "R",
                "diningOptions": "dine-in",
                "address": "a",
                "city": "c",
            },
        )
        assert resp2.status_code == 400
