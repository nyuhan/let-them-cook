import json
from app import snake_to_camel


# ---------------------------------------------------------------------------
# snake_to_camel helper
# ---------------------------------------------------------------------------


class TestSnakeToCamel:
    def test_basic_conversion(self):
        assert snake_to_camel({"map_uri": "x"}) == {"mapUri": "x"}

    def test_single_word_unchanged(self):
        assert snake_to_camel({"name": "x"}) == {"name": "x"}

    def test_multiple_underscores(self):
        result = snake_to_camel({"long_snake_case_key": 1})
        assert result == {"longSnakeCaseKey": 1}

    def test_empty_dict(self):
        assert snake_to_camel({}) == {}


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


class TestIndex:
    def test_index_renders(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Let Them Cook" in resp.data


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


# ---------------------------------------------------------------------------
# GET /api/restaurants (list)
# ---------------------------------------------------------------------------


class TestListRestaurants:
    def test_empty(self, client):
        resp = client.get("/api/restaurants")
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_camel_case_keys(self, client, seed_restaurant):
        seed_restaurant()
        listing = client.get("/api/restaurants").get_json()
        r = listing[0]
        assert "mapUri" in r
        assert "directionsUri" in r
        assert "priceLevel" in r
        assert "createdAt" in r
        assert "openingHours" in r
        assert "types" in r
        assert "wishlisted" in r

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
    def test_found(self, client, seed_restaurant):
        seed_restaurant(id="r1")
        resp = client.get("/api/restaurants/r1")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["id"] == "r1"
        assert "mapUri" in data  # camelCase
        assert data["wishlisted"] is False

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

    def test_promote_wishlisted_to_visited(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
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

    def test_cannot_demote_visited_to_wishlisted(self, client, seed_restaurant):
        seed_restaurant(id="r1", rating=4)
        resp = client.put("/api/restaurants/r1", json={"wishlisted": True})
        assert resp.status_code == 400
        assert "wishlisted" in resp.get_json()["error"]

    def test_cannot_add_rating_to_wishlisted(self, client, seed_restaurant):
        seed_restaurant(id="r1", wishlisted=True, rating=None)
        resp = client.put("/api/restaurants/r1", json={"rating": 4})
        assert resp.status_code == 400


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
