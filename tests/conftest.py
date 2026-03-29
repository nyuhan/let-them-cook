import sqlite3
import pytest
import app as app_module
from app import app as flask_app

_TEST_PASSWORD = "letthemcook"


@pytest.fixture()
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    app_module.DATABASE = db_path
    flask_app.secret_key = "test-secret-key"
    flask_app.config.update({"TESTING": True})

    # Initialize DB and override password for tests
    conn = sqlite3.connect(db_path)
    app_module._init_db(conn)
    conn.close()

    yield flask_app


@pytest.fixture()
def client(app):
    with app.test_client() as c:
        c.post("/login", data={"password": _TEST_PASSWORD, "totp_code": ""})
        yield c


@pytest.fixture()
def seed_restaurant(client):
    """Helper that inserts a restaurant and returns its data dict."""

    def _seed(**overrides):
        created_at = overrides.pop("created_at", None)
        data = {
            "id": "place_abc",
            "name": "Test Restaurant",
            "diningOptions": "dine-in",
            "rating": 4,
            "address": "123 Main St",
            "city": "TestCity",
            "mapUri": "https://maps.example.com/place",
            "directionsUri": "https://maps.example.com/dir",
            "priceLevel": 2,
            "notes": "Great place",
            "types": [],
        }
        data.update(overrides)
        resp = client.post("/api/restaurants", json=data)
        if created_at is not None:
            connection = sqlite3.connect(app_module.DATABASE)
            connection.execute(
                "UPDATE restaurants SET created_at = ? WHERE id = ?",
                (created_at, data["id"]),
            )
            connection.commit()
            connection.close()
        return data, resp

    return _seed
