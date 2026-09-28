"""Utility untuk meratakan (inline) JSON schema pydantic.

Beberapa provider LLM OpenAI-compatible (mis. Databricks Foundation Model
API) menolak JSON schema yang memakai `$ref` ke `$defs` untuk model nested
(error: "Invalid JSON schema - /$defs/<Model>"). Fungsi di sini meng-resolve
semua `$ref` menjadi salinan literal skema tujuannya, lalu membuang `$defs`,
supaya skema tetap valid untuk provider yang tidak mendukung composition/$ref.
"""

from __future__ import annotations

import copy
from typing import Any

from pydantic import BaseModel


def inline_json_schema_refs(model: type[BaseModel]) -> dict[str, Any]:
    """Kembalikan JSON schema `model` dengan semua `$ref` di-inline.

    Args:
        model: Kelas pydantic yang akan diambil skemanya.

    Returns:
        Dict JSON schema tanpa key `$defs`/`$ref` (semua sudah diratakan).
    """
    schema = model.model_json_schema()
    defs: dict[str, Any] = schema.pop("$defs", {})

    def _resolve(node: Any, stack: tuple[str, ...]) -> Any:
        if isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref.startswith("#/$defs/"):
                def_name = ref.removeprefix("#/$defs/")
                if def_name in stack:
                    # Hindari recursion tak terbatas untuk skema circular.
                    return {"type": "object"}
                target = defs.get(def_name)
                if target is None:
                    return node
                return _resolve(copy.deepcopy(target), stack + (def_name,))
            return {key: _resolve(value, stack) for key, value in node.items()}
        if isinstance(node, list):
            return [_resolve(item, stack) for item in node]
        return node

    return _resolve(schema, ())
