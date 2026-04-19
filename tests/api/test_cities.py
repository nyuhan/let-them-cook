"""
Tests for GET /api/cities.
"""

import json
import sqlite3
import app as app_module


# ---------------------------------------------------------------------------
# GET /api/cities
# ---------------------------------------------------------------------------


class TestGetCities:
    def test_empty_db(self, client):
        resp = client.get("/api/cities")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_returns_distinct_sorted(self, client, seed_restaurant):
        seed_restaurant(id="r1", city="Zurich")
        seed_restaurant(id="r2", city="Amsterdam")
        seed_restaurant(id="r3", city="Zurich")  # duplicate
        resp = client.get("/api/cities")
        assert resp.get_json() == ["Amsterdam", "Zurich"]

