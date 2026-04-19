import app as app_module
from app import app as flask_app


class TestSchema:
    def test_tables_created(self, client):
        with flask_app.app_context():
            db = app_module.get_db()
            cur = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN ('restaurants','dishes') ORDER BY name"
            )
            tables = [row[0] for row in cur.fetchall()]
            assert "dishes" in tables
            assert "restaurants" in tables

    def test_restaurant_columns(self, client):
        expected = {
            "id",
            "name",
            "address",
            "city",
            "map_uri",
            "directions_uri",
            "dining_options",
            "rating",
            "created_at",
            "price_level",
            "notes",
            "opening_hours",
            "types",
            "latitude",
            "longitude",
        }
        with flask_app.app_context():
            db = app_module.get_db()
            cur = db.execute("PRAGMA table_info(restaurants)")
            columns = {row["name"] for row in cur.fetchall()}
            assert expected.issubset(columns)

    def test_dishes_columns(self, client):
        expected = {"restaurant_id", "name", "rating", "notes", "created_at"}
        with flask_app.app_context():
            db = app_module.get_db()
            cur = db.execute("PRAGMA table_info(dishes)")
            columns = {row["name"] for row in cur.fetchall()}
            assert expected.issubset(columns)

    def test_migration_idempotent(self, client):
        """Calling get_db() multiple times in the same context must not error."""
        with flask_app.app_context():
            db1 = app_module.get_db()
            # Force a second init by clearing the cached db
            from flask import g

            g._database = None
            db2 = app_module.get_db()
            # Both should work fine
            cur = db2.execute("SELECT count(*) FROM restaurants")
            assert cur.fetchone()[0] == 0
