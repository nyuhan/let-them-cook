import os
import tempfile
import pytest
from app import app as flask_app


@pytest.fixture()
def app(tmp_path):
    db_path = str(tmp_path / "test.db")
    os.environ['SQLITE_FILE_PATH'] = db_path

    # Re-import to pick up the new DATABASE path at module level
    import app as app_module
    app_module.DATABASE = db_path

    flask_app.config.update({"TESTING": True})
    yield flask_app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def seed_restaurant(client):
    """Helper that inserts a restaurant and returns its data dict."""
    def _seed(**overrides):
        data = {
            "id": "place_abc",
            "name": "Test Restaurant",
            "type": "dine-in",
            "rating": 4,
            "address": "123 Main St",
            "city": "TestCity",
            "mapUri": "https://maps.example.com/place",
            "directionsUri": "https://maps.example.com/dir",
            "priceLevel": 2,
            "notes": "Great place",
        }
        data.update(overrides)
        resp = client.post("/api/restaurants", json=data)
        return data, resp
    return _seed
