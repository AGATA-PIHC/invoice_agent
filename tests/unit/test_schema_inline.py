from __future__ import annotations

import json

from baca_invoice.models.travel_document import TravelDocumentResult
from baca_invoice.utils.schema_inline import inline_json_schema_refs


def test_inline_json_schema_refs_removes_defs_and_refs():
    schema = inline_json_schema_refs(TravelDocumentResult)
    dumped = json.dumps(schema)
    assert "$defs" not in schema
    assert "$ref" not in dumped


def test_inline_json_schema_refs_preserves_nested_line_item_fields():
    schema = inline_json_schema_refs(TravelDocumentResult)
    line_items = schema["properties"]["line_items"]
    item_schema = line_items["items"]
    assert item_schema["type"] == "object"
    assert set(item_schema["properties"]) == {
        "description",
        "quantity",
        "unit_price",
        "subtotal",
    }


def test_inline_json_schema_refs_preserves_authenticity_fields():
    schema = inline_json_schema_refs(TravelDocumentResult)
    auth_schema = schema["properties"]["authenticity"]
    assert auth_schema["type"] == "object"
    assert "is_suspicious" in auth_schema["properties"]


def test_inline_json_schema_refs_nested_object_still_flattenable():
    """Semua nested object (bukan hanya top-level) harus bebas $ref/$defs,
    supaya provider ADK bisa menambahkan additionalProperties/required tanpa
    perlu resolve $ref lagi (lihat google.adk.models.lite_llm._enforce_strict_openai_schema).
    """
    schema = inline_json_schema_refs(TravelDocumentResult)

    def _walk(node):
        if isinstance(node, dict):
            assert "$ref" not in node
            for value in node.values():
                _walk(value)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(schema)
