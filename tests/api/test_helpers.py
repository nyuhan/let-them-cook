"""
Unit tests for the snake_to_camel helper.
"""

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

