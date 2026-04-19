"""
Tests for GET /api/restaurants and GET /api/restaurants/<id>.
"""

import json
import sqlite3
import app as app_module
from app import snake_to_camel


# ---------------------------------------------------------------------------
# GET /api/restaurants (list)
# ---------------------------------------------------------------------------


class TestListRestaurants:
    def test_empty(self, client):
        resp = client.get("/api/restaurants")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_success(self, client, seed_restaurant):
        seed_restaurant()
        r = client.get("/api/restaurants").get_json()[0]
        assert r["id"] == "place_abc"
        assert r["name"] == "Test Restaurant"
        assert r["address"] == "123 Main St"
        assert r["city"] == "TestCity"
        assert r["mapUri"] == "https://maps.example.com/place"
        assert r["directionsUri"] == "https://maps.example.com/dir"
        assert r["diningOptions"] == "dine-in"
        assert r["priceLevel"] == 2
        assert r["notes"] == "Great place"
        assert r["types"] == ["restaurant"]
        assert r["cuisines"] == []
        assert r["openingHours"] is None
        assert r["dishes"] == []
        assert r["wishlisted"] is False
        assert r["rating"] == 4
        assert r["latitude"] == 48.8566
        assert r["longitude"] == 2.3522
        assert "createdAt" in r

    def test_includes_dishes(self, client, seed_restaurant):
        seed_restaurant(dishes=[{"name": "Tacos", "rating": 1}])
        listing = client.get("/api/restaurants").get_json()
        assert "dishes" in listing[0]
        assert listing[0]["dishes"][0]["name"] == "Tacos"

    def test_opening_hours_deserialized(self, client, seed_restaurant):
        hours = {"weekdayDescriptions": ["Mon: 9–5"], "periods": []}
        seed_restaurant(openingHours=hours)
        listing = client.get("/api/restaurants").get_json()
        assert listing[0]["openingHours"] == hours

    def test_types_deserialized(self, client, seed_restaurant):
        types = ["restaurant", "japanese_restaurant"]
        seed_restaurant(types=types)
        listing = client.get("/api/restaurants").get_json()
        assert listing[0]["types"] == types

    def test_ordered_by_created_at_desc(self, client, seed_restaurant):
        seed_restaurant(id="aaa", name="First", created_at="2025-01-01 10:00:00")
        seed_restaurant(id="zzz", name="Second", created_at="2025-01-02 10:00:00")
        listing = client.get("/api/restaurants").get_json()
        assert listing[0]["name"] == "Second"
        assert listing[1]["name"] == "First"

    def test_wishlisted_in_list(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        seed_restaurant(id="r2", wishlisted=True, rating=None)
        listing = client.get("/api/restaurants").get_json()
        by_id = {r["id"]: r for r in listing}
        assert by_id["r1"]["wishlisted"] is False
        assert by_id["r2"]["wishlisted"] is True
        assert by_id["r2"]["rating"] is None


# ---------------------------------------------------------------------------
# GET /api/restaurants/<id>
# ---------------------------------------------------------------------------


class TestGetRestaurant:
    def test_success(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.get("/api/restaurants/r1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "r1"
        assert data["name"] == "Test Restaurant"
        assert data["address"] == "123 Main St"
        assert data["city"] == "TestCity"
        assert data["mapUri"] == "https://maps.example.com/place"
        assert data["directionsUri"] == "https://maps.example.com/dir"
        assert data["diningOptions"] == "dine-in"
        assert data["priceLevel"] == 2
        assert data["notes"] == "Great place"
        assert data["types"] == ["restaurant"]
        assert data["cuisines"] == []
        assert data["openingHours"] is None
        assert data["dishes"] == []
        assert data["wishlisted"] is False
        assert data["rating"] == 4
        assert data["latitude"] == 48.8566
        assert data["longitude"] == 2.3522
        assert "createdAt" in data

    def test_opening_hours_deserialized(self, client, seed_restaurant):
        hours = {"weekdayDescriptions": ["Mon: 9–5"], "periods": []}
        seed_restaurant(id="r1", openingHours=hours)
        resp = client.get("/api/restaurants/r1")
        assert resp.get_json()["openingHours"] == hours

    def test_types_returned(self, client, seed_restaurant):
        types = ["restaurant", "korean_restaurant"]
        seed_restaurant(id="r1", types=types)
        resp = client.get("/api/restaurants/r1")
        assert resp.get_json()["types"] == types

    def test_not_found(self, client):
        resp = client.get("/api/restaurants/nonexistent")
        assert resp.status_code == 404

    def test_wishlisted_restaurant(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        data = client.get("/api/restaurants/r1").get_json()
        assert data["wishlisted"] is True
        assert data["rating"] is None
