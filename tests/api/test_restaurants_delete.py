"""
Tests for DELETE /api/restaurants/<id>.
"""

import json
import sqlite3
import app as app_module
from app import snake_to_camel


# ---------------------------------------------------------------------------
# DELETE /api/restaurants/<id>
# ---------------------------------------------------------------------------


class TestDeleteRestaurant:
    def test_success(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.delete("/api/restaurants/r1")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"
        # Confirm gone
        assert client.get("/api/restaurants/r1").status_code == 404

    def test_not_found(self, client):
        resp = client.delete("/api/restaurants/missing")
        assert resp.status_code == 404

    def test_delete_wishlisted_restaurant(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        resp = client.delete("/api/restaurants/r1")
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "deleted"
        assert client.get("/api/restaurants/r1").status_code == 404


