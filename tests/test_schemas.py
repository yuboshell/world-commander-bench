"""Tests for the output-schema parsers (verbose JSON vs terse formats)."""
from arena.model_client import SCHEMAS


def parse(name, text):
    return SCHEMAS[name].parse(text)


def test_json_schema():
    assert parse("json", '[{"agent":"red","dir":"N"}]') == {("red", "N")}
    assert parse("json", 'Moves: [{"agent":"red","dir":"n"},{"agent":"blue","dir":"S"}]') \
        == {("red", "N"), ("blue", "S")}


def test_pairs_schema():
    assert parse("pairs", "red:N blue:S") == {("red", "N"), ("blue", "S")}
    assert parse("pairs", "Moves: red:n, blue:s.") == {("red", "N"), ("blue", "S")}
    assert parse("pairs", "red:Q blue:N") == {("blue", "N")}   # Q is not a direction


def test_grouped_schema():
    # all named agents move the same direction: "N: red blue green"
    assert parse("grouped", "N: red blue green") \
        == {("red", "N"), ("blue", "N"), ("green", "N")}
    assert parse("grouped", "S: yellow") == {("yellow", "S")}
    assert parse("grouped", "N: red, blue") == {("red", "N"), ("blue", "N")}


def test_all_schemas_registered_with_system_prompts():
    for name in ("json", "pairs", "grouped"):
        assert SCHEMAS[name].system and callable(SCHEMAS[name].parse)
