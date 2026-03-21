import os
import threading
import requests
import time
import pytest
from werkzeug.serving import make_server

from app import app as flask_app
import app as app_module


@pytest.fixture()
def live_server(tmp_path):
    """Start a real Flask server on a random port with a fresh temp DB."""
    db_path = str(tmp_path / "e2e_test.db")
    os.environ["SQLITE_FILE_PATH"] = db_path
    app_module.DATABASE = db_path

    flask_app.config.update({"TESTING": False})

    server = make_server("127.0.0.1", 0, flask_app)
    port = server.server_address[1]
    base_url = f"http://127.0.0.1:{port}"

    thread = threading.Thread(target=server.serve_forever)
    thread.daemon = True
    thread.start()

    # Wait for server to be ready
    for _ in range(100):
        try:
            requests.get(f"{base_url}/api/cities", timeout=2)
            break
        except requests.exceptions.RequestException:
            time.sleep(0.1)

    yield base_url

    server.shutdown()


@pytest.fixture()
def seed(live_server):
    """Factory to POST a restaurant to the live server. Returns the data dict."""
    def _seed(**overrides):
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
        resp = requests.post(f"{live_server}/api/restaurants", json=data)
        assert resp.status_code == 201, f"Seed failed: {resp.text}"
        return data
    return _seed


@pytest.fixture()
def page(page):
    """Override default Playwright page timeout (30s → 10s)."""
    page.set_default_timeout(10000)
    return page
