# Let Them Cook

A simple Flask application to record and manage your favorite restaurants. Features include restaurant details, ratings, types (dine-in/delivery), and city filtering, powered by Google Places API and SQLite.

## Running Locally

### Prerequisites

* Python 3.9+
* A Google Maps API Key with **Places API** and **Maps JavaScript API** enabled.

### Setup

1. **Create a virtual environment and install dependencies**:

    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    ```

1. **Configure Environment Variables**:
    Create a `.env` file in the project root and add your Google Maps API key:

    ```bash
    echo 'GOOGLE_MAPS_API_KEY="YOUR_API_KEY"' > .env
    ```

1. **Run the application**:

    ```bash
    python app.py
    ```

1. **Access the app**:
    Open [http://localhost:5000](http://localhost:5000) in your browser.

    *Note: Data will be stored in `instance/restaurants.db` by default.*

---

## Running with Docker

### Prerequisites

* Docker installed on your machine.
* A Google Maps API Key.

### Build and Run

1. **Build the Docker image**:

    ```bash
    docker build -t let-them-cook .
    ```

1. **Run the container**:
    You **must** provide the API key as an environment variable and mount the data volume to `/data`.

    ```bash
    docker run -p 5000:5000 \
      -e GOOGLE_MAPS_API_KEY="YOUR_API_KEY" \
      -v YOUR_DATA_DIR:/data \
      let-them-cook
    ```

1. **Access the app**:
    Open [http://localhost:5000](http://localhost:5000) in your browser.

## API Endpoints

* `GET /api/restaurants` — Returns a list of all recorded restaurants.
* `POST /api/restaurants` — Add a new restaurant.
  * Body: `{ "name": "...", "type": "dine-in|delivery|both", "rating": 1-5, ... }`
* `PUT /api/restaurants/<id>` — Update an existing restaurant.
* `DELETE /api/restaurants/<id>` — Delete a restaurant.
* `GET /api/cities` — Returns a list of distinct cities from the stored restaurants.

## Testing

### Prerequisites

All test dependencies are installed inside the virtual environment:

```bash
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium
```

### Run all tests (unit + E2E)

```bash
pytest
```

This runs backend unit tests and offline E2E browser tests. Google Maps tests are excluded by default.

### Run only backend unit tests

```bash
pytest tests/test_app.py -v
```

### Run only E2E browser tests

```bash
pytest tests/e2e/ -v
```

### Run with visible browser (headed mode)

```bash
pytest tests/e2e/ -v --headed --slowmo=500
```

### Run a specific test

```bash
pytest tests/e2e/ -k "TestDishAdd" -v
```

### Run Google Maps integration test

Requires a valid `GOOGLE_MAPS_API_KEY` in `.env` and network access:

```bash
pytest tests/e2e/ -m google_maps -v
```
