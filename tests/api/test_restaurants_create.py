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
        assert body["wishlisted"] is False
        assert body["rating"] == 4
        # Verify it's persisted
        listing = client.get("/api/restaurants").get_json()
        assert len(listing) == 1
        assert listing[0]["name"] == "Test Restaurant"

    def test_with_dishes(self, client, seed_restaurant):
        dishes = [
            {"name": "Pizza", "rating": 1, "notes": "good"},
            {"name": "Pasta", "rating": 0, "notes": "meh"},
        ]
        data, resp = seed_restaurant(dishes=dishes)
        assert resp.status_code == 201
        listing = client.get("/api/restaurants").get_json()
        assert len(listing[0]["dishes"]) == 2

    def test_with_opening_hours(self, client, seed_restaurant):
        hours = {"weekdayDescriptions": ["Monday: 9 AM – 5 PM"], "periods": []}
        data, resp = seed_restaurant(openingHours=hours)
        assert resp.status_code == 201
        listing = client.get("/api/restaurants").get_json()
        assert listing[0]["openingHours"] == hours

    def test_with_types(self, client, seed_restaurant):
        types = ["restaurant", "food", "italian_restaurant"]
        data, resp = seed_restaurant(types=types)
        assert resp.status_code == 201
        listing = client.get("/api/restaurants").get_json()
        assert listing[0]["types"] == types

    def test_types_default_empty(self, client, seed_restaurant):
        data, resp = seed_restaurant(types=None)
        assert resp.status_code == 201
        listing = client.get("/api/restaurants").get_json()
        assert listing[0]["types"] == []

    def test_invalid_rating_string(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "R",
                "diningOptions": "dine-in",
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
                "diningOptions": "dine-in",
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
                "diningOptions": "dine-in",
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
                "diningOptions": "takeaway",
                "rating": 3,
                "address": "a",
                "city": "c",
            },
        )
        assert resp.status_code == 400

    def test_missing_name(self, client):
        resp = client.post(
            "/api/restaurants",
            json={
                "id": "x",
                "name": "",
                "diningOptions": "dine-in",
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
        listing = client.get("/api/restaurants").get_json()
        # Only "Good" should have been inserted
        assert len(listing[0]["dishes"]) == 1
        assert listing[0]["dishes"][0]["name"] == "Good"

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
