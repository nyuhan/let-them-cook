"""
Tests for PUT /api/restaurants/<id>.
"""

import json
import sqlite3
import app as app_module
from app import snake_to_camel


# ---------------------------------------------------------------------------
# PUT /api/restaurants/<id>
# ---------------------------------------------------------------------------


class TestUpdateRestaurant:
    def test_partial_update(self, client, seed_restaurant):
        seed_restaurant(id="r1", rating=3)
        resp = client.put("/api/restaurants/r1", json={"rating": 5})
        assert resp.status_code == 200
        # Verify the rating changed but other fields stayed
        r = client.get("/api/restaurants/r1").get_json()
        assert r["rating"] == 5
        assert r["name"] == "Test Restaurant"

    def test_full_update(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        hours = {"weekdayDescriptions": ["Mon: 10–6"], "periods": []}
        types = ["restaurant", "french_restaurant"]
        resp = client.put(
            "/api/restaurants/r1",
            json={
                "name": "Updated",
                "diningOptions": "delivery",
                "rating": 2,
                "notes": "new notes",
                "address": "456 New St",
                "city": "NewCity",
                "mapUri": "https://new.map",
                "directionsUri": "https://new.dir",
                "priceLevel": 3,
                "openingHours": hours,
                "types": types,
                "latitude": 51.5074,
                "longitude": -0.1278,
            },
        )
        assert resp.status_code == 200
        # Use list endpoint which correctly deserializes opening_hours
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        assert r["name"] == "Updated"
        assert r["diningOptions"] == "delivery"
        assert r["rating"] == 2
        assert r["city"] == "NewCity"
        assert r["priceLevel"] == 3
        assert r["openingHours"] == hours
        assert r["types"] == types
        assert r["latitude"] == 51.5074
        assert r["longitude"] == -0.1278

    def test_types_update(self, client, seed_restaurant):
        seed_restaurant(id="r1", types=["restaurant"])
        resp = client.put(
            "/api/restaurants/r1", json={"types": ["restaurant", "sushi_restaurant"]}
        )
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        assert r["types"] == ["restaurant", "sushi_restaurant"]

    def test_types_preserved_when_not_in_payload(self, client, seed_restaurant):
        seed_restaurant(id="r1", types=["restaurant", "thai_restaurant"])
        resp = client.put("/api/restaurants/r1", json={"rating": 5})
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        assert r["types"] == ["restaurant", "thai_restaurant"]

    def test_not_found(self, client):
        resp = client.put("/api/restaurants/missing", json={"rating": 3})
        assert resp.status_code == 404

    def test_invalid_rating(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.put("/api/restaurants/r1", json={"rating": "bad"})
        assert resp.status_code == 400

    def test_rating_out_of_range(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.put("/api/restaurants/r1", json={"rating": 10})
        assert resp.status_code == 400

    def test_invalid_type(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.put("/api/restaurants/r1", json={"diningOptions": "takeaway"})
        assert resp.status_code == 400

    def test_dishes_insert(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.put(
            "/api/restaurants/r1",
            json={
                "dishes": [{"name": "Burger", "rating": 1, "notes": "juicy"}],
            },
        )
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        assert len(r["dishes"]) == 1
        assert r["dishes"][0]["name"] == "Burger"

    def test_dishes_update(self, client, seed_restaurant):
        seed_restaurant(id="r1", dishes=[{"name": "Burger", "rating": 1}])
        listing = client.get("/api/restaurants").get_json()
        dish_id = listing[0]["dishes"][0]["id"]

        resp = client.put(
            "/api/restaurants/r1",
            json={
                "dishes": [
                    {
                        "id": dish_id,
                        "name": "Cheeseburger",
                        "rating": 0,
                        "notes": "updated",
                    }
                ],
            },
        )
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        assert r["dishes"][0]["name"] == "Cheeseburger"
        assert r["dishes"][0]["rating"] == 0

    def test_dishes_update_preserves_order(self, client, seed_restaurant):
        seed_restaurant(
            id="r1",
            dishes=[
                {"name": "Alpha", "rating": 1, "notes": "first"},
                {"name": "Bravo", "rating": 0, "notes": "second"},
                {"name": "Charlie", "rating": 1, "notes": "third"},
            ],
        )
        listing = client.get("/api/restaurants").get_json()
        dishes = listing[0]["dishes"]
        bravo_id = next(d["id"] for d in dishes if d["name"] == "Bravo")

        resp = client.put(
            "/api/restaurants/r1",
            json={
                "dishes": [
                    {
                        "id": dishes[0]["id"],
                        "name": "Alpha",
                        "rating": 1,
                        "notes": "first",
                    },
                    {
                        "id": bravo_id,
                        "name": "Bravo-Renamed",
                        "rating": 1,
                        "notes": "updated note",
                    },
                    {
                        "id": dishes[2]["id"],
                        "name": "Charlie",
                        "rating": 1,
                        "notes": "third",
                    },
                ],
            },
        )
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        names = [d["name"] for d in r["dishes"]]
        assert names == ["Alpha", "Bravo-Renamed", "Charlie"]
        updated = next(d for d in r["dishes"] if d["name"] == "Bravo-Renamed")
        assert updated["rating"] == 1
        assert updated["notes"] == "updated note"

    def test_dishes_delete(self, client, seed_restaurant):
        seed_restaurant(
            id="r1",
            dishes=[
                {"name": "A", "rating": 1},
                {"name": "B", "rating": 0},
            ],
        )
        listing = client.get("/api/restaurants").get_json()
        assert len(listing[0]["dishes"]) == 2

        # Send update with empty dishes list → should delete both
        resp = client.put("/api/restaurants/r1", json={"dishes": []})
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        assert len(listing[0]["dishes"]) == 0

    def test_dishes_mixed_operations(self, client, seed_restaurant):
        seed_restaurant(
            id="r1",
            dishes=[
                {"name": "Keep", "rating": 1},
                {"name": "Remove", "rating": 0},
            ],
        )
        listing = client.get("/api/restaurants").get_json()
        dishes = listing[0]["dishes"]
        keep_id = next(d["id"] for d in dishes if d["name"] == "Keep")

        resp = client.put(
            "/api/restaurants/r1",
            json={
                "dishes": [
                    {"id": keep_id, "name": "Kept-Updated", "rating": 0},  # update
                    {"name": "NewDish", "rating": 1},  # insert
                    # "Remove" is omitted → delete
                ],
            },
        )
        assert resp.status_code == 200
        listing = client.get("/api/restaurants").get_json()
        r = next(x for x in listing if x["id"] == "r1")
        dishes = r["dishes"]
        assert len(dishes) == 2
        assert dishes[0]["name"] == "Kept-Updated"
        assert dishes[0]["rating"] == 0
        assert dishes[0]["notes"] is None
        assert dishes[1]["name"] == "NewDish"
        assert dishes[1]["rating"] == 1
        assert dishes[1]["notes"] is None

    def test_duplicate_dish_name_on_insert_rejected(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.put(
            "/api/restaurants/r1",
            json={
                "dishes": [
                    {"name": "Burger", "rating": 1},
                    {"name": "Burger", "rating": 0},
                ]
            },
        )
        assert resp.status_code == 400
        assert "Duplicate dish: Burger" in resp.get_json()["error"]

    def test_duplicate_dish_name_on_update_rejected(self, client, seed_restaurant):
        seed_restaurant(
            id="r1",
            dishes=[
                {"name": "Burger", "rating": 1},
                {"name": "Fries", "rating": 1},
            ],
        )
        listing = client.get("/api/restaurants").get_json()
        dishes = listing[0]["dishes"]
        burger_id = next(d["id"] for d in dishes if d["name"] == "Burger")
        fries_id = next(d["id"] for d in dishes if d["name"] == "Fries")

        # Rename both dishes to the same name
        resp = client.put(
            "/api/restaurants/r1",
            json={
                "dishes": [
                    {"id": burger_id, "name": "Samename", "rating": 1},
                    {"id": fries_id, "name": "Samename", "rating": 1},
                ]
            },
        )
        assert resp.status_code == 400
        assert "Duplicate dish: Samename" in resp.get_json()["error"]

    def test_promote_wishlisted_to_visited(self, client, seed_restaurant):
        seed_restaurant(
            id="r1", wishlisted=True, rating=None, created_at="2020-01-01 00:00:00"
        )
        resp = client.put(
            "/api/restaurants/r1", json={"wishlisted": False, "rating": 4}
        )
        assert resp.status_code == 200
        r = resp.get_json()
        assert r["wishlisted"] is False
        assert r["rating"] == 4
        # Also reflected in the list
        listing = client.get("/api/restaurants").get_json()
        r_list = next(x for x in listing if x["id"] == "r1")
        assert r_list["wishlisted"] is False
        assert r_list["rating"] == 4
        # created_at should be reset so the newly-visited restaurant sorts to the top
        conn = sqlite3.connect(app_module.DATABASE)
        row = conn.execute(
            "SELECT created_at FROM restaurants WHERE id = 'r1'"
        ).fetchone()
        conn.close()
        assert row[0] is not None
        assert row[0] != "2020-01-01 00:00:00"

    def test_cannot_demote_visited_to_wishlisted(self, client, seed_restaurant):
        seed_restaurant(id="r1", rating=4)
        resp = client.put("/api/restaurants/r1", json={"wishlisted": True})
        assert resp.status_code == 400
        assert "wishlisted" in resp.get_json()["error"]

    def test_cannot_add_rating_to_wishlisted(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        resp = client.put("/api/restaurants/r1", json={"rating": 4})
        assert resp.status_code == 400

    def test_update_fields_on_wishlisted_restaurant(self, client, seed_restaurant):
        seed_restaurant(
            id="r1", wishlisted=True, rating=None, notes="old", diningOptions="dine-in"
        )
        resp = client.put(
            "/api/restaurants/r1", json={"notes": "new", "diningOptions": "delivery"}
        )
        assert resp.status_code == 200
        r = resp.get_json()
        assert r["wishlisted"] is True
        assert r["rating"] is None
        assert r["notes"] == "new"
        assert r["diningOptions"] == "delivery"

    def test_mark_visited_rejects_invalid_rating(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        resp = client.put(
            "/api/restaurants/r1", json={"wishlisted": False, "rating": 6}
        )
        assert resp.status_code == 400
        # restaurant is unchanged
        r = client.get("/api/restaurants/r1").get_json()
        assert r["wishlisted"] is True
        assert r["rating"] is None

    def test_mark_visited_rejects_zero_rating(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        resp = client.put(
            "/api/restaurants/r1", json={"wishlisted": False, "rating": 0}
        )
        assert resp.status_code == 400

    def test_mark_visited_persists_rating(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        resp = client.put(
            "/api/restaurants/r1", json={"wishlisted": False, "rating": 3}
        )
        assert resp.status_code == 200
        r = client.get("/api/restaurants/r1").get_json()
        assert r["wishlisted"] is False
        assert r["rating"] == 3
