import os
import sqlite3
import pytest
from werkzeug.security import generate_password_hash
import app as app_module
from app import app as flask_app

_TEST_PASSWORD = "test-password-abc"


@pytest.fixture()
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ["SQLITE_FILE_PATH"] = db_path
    app_module.DATABASE = db_path
    flask_app.secret_key = "test-secret-key"
    flask_app.config.update({"TESTING": True})

    # Seed settings table with known password, no TOTP
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            secret_key TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            totp_secret TEXT
        )"""
    )
    conn.execute(
        "INSERT OR IGNORE INTO settings (id, secret_key, password_hash, totp_secret) VALUES (1, ?, ?, NULL)",
        ("test-secret-key", generate_password_hash(_TEST_PASSWORD)),
    )
    conn.commit()
    conn.close()

    yield flask_app

    os.environ.pop("SQLITE_FILE_PATH", None)


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
