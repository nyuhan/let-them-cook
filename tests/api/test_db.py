import sqlite3
import app as app_module
from app import app as flask_app


class TestSchema:
    def test_tables_created(self, client):
        with flask_app.app_context():
            db = app_module.get_db()
            cur = db.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = 'restaurants'"
            )
            tables = [row[0] for row in cur.fetchall()]
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
            "dishes",
        }
        with flask_app.app_context():
            db = app_module.get_db()
            cur = db.execute("PRAGMA table_info(restaurants)")
            columns = {row["name"] for row in cur.fetchall()}
            assert expected.issubset(columns)

    def test_dishes_stored_as_json_column(self, client):
        with flask_app.app_context():
            db = app_module.get_db()
            cur = db.execute("PRAGMA table_info(restaurants)")
            columns = {row["name"] for row in cur.fetchall()}
            assert "dishes" in columns

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

    def test_empty_string_notes_migrated_to_null(self, app):
        """_init_db normalises pre-existing empty-string notes to NULL."""
        conn = sqlite3.connect(app_module.DATABASE)
        conn.execute(
            "INSERT INTO restaurants (id, name, address, city, dining_options, rating, wishlisted, notes)"
            " VALUES ('r1','X','A','C','dine-in',3,0,'')"
        )
        conn.commit()
        conn.close()

        # Re-running _init_db (as happens on every startup) should fix it
        conn2 = sqlite3.connect(app_module.DATABASE)
        app_module._init_db(conn2)
        conn2.close()

        conn3 = sqlite3.connect(app_module.DATABASE)
        row = conn3.execute("SELECT notes FROM restaurants WHERE id='r1'").fetchone()
        conn3.close()
        assert row[0] is None
