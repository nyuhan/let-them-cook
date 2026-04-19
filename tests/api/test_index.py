"""
Tests for GET /.
"""

import json
import sqlite3
import app as app_module


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


class TestIndex:
    def test_index_renders(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert b"Let Them Cook" in resp.data

