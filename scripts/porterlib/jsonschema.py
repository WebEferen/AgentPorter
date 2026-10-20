"""Validator for the JSON Schema subset AgentPorter's schemas use.

Supported: type, enum, const, required, properties, additionalProperties,
items, minItems, minLength, minimum, maximum, pattern, anyOf, oneOf, allOf,
and $ref to "#/..." or "<file>.schema.json#/..." inside knowledge/schemas.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .common import SCHEMAS, PorterError, read_json

_TYPES = {
    "object": dict,
    "array": list,
    "string": str,
    "boolean": bool,
    "null": type(None),
}

_cache: dict[str, Any] = {}


def load_schema(name: str) -> Any:
    file = name if name.endswith(".json") else f"{name}.schema.json"
    if file not in _cache:
        path = SCHEMAS / file
        if not path.exists():
            raise PorterError(f"unknown schema: {name}")
        _cache[file] = read_json(path)
    return _cache[file]


def _type_ok(value: Any, expected: str) -> bool:
    if isinstance(value, bool):
        return expected == "boolean"
    if expected == "integer":
        return isinstance(value, int)
    if expected == "number":
        return isinstance(value, (int, float))
    py = _TYPES.get(expected)
    return True if py is None else isinstance(value, py)


def _resolve(ref: str, root: Any, root_file: str) -> tuple[Any, Any, str]:
    file_part, _, pointer = ref.partition("#")
    if file_part:
        root = load_schema(file_part)
        root_file = file_part
    node = root
    for part in [p for p in pointer.split("/") if p]:
        node = node[part.replace("~1", "/").replace("~0", "~")]
    return node, root, root_file


def validate(value: Any, schema: Any, root: Any = None, root_file: str = "", path: str = "$") -> list[str]:
    root = schema if root is None else root
    errors: list[str] = []
    if schema is True or schema == {}:
        return errors
    if "$ref" in schema:
        target, new_root, new_file = _resolve(schema["$ref"], root, root_file)
        return validate(value, target, new_root, new_file, path)
    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return [f"{path}: expected {'/'.join(types)}, got {type(value).__name__}"]
    if "const" in schema and value != schema["const"]:
        errors.append(f"{path}: expected {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: {value!r} not in {schema['enum']}")
    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: shorter than {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append(f"{path}: {value!r} does not match {schema['pattern']}")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append(f"{path}: below minimum {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            errors.append(f"{path}: above maximum {schema['maximum']}")
    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append(f"{path}: missing required '{key}'")
        props = schema.get("properties", {})
        for key, sub in props.items():
            if key in value:
                errors.extend(validate(value[key], sub, root, root_file, f"{path}.{key}"))
        extra = schema.get("additionalProperties", True)
        if extra is not True:
            for key in value:
                if key in props:
                    continue
                if extra is False:
                    errors.append(f"{path}: unexpected property '{key}'")
                else:
                    errors.extend(validate(value[key], extra, root, root_file, f"{path}.{key}"))
    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} items")
        if "items" in schema:
            for i, item in enumerate(value):
                errors.extend(validate(item, schema["items"], root, root_file, f"{path}[{i}]"))
    if "allOf" in schema:
        for sub in schema["allOf"]:
            errors.extend(validate(value, sub, root, root_file, path))
    if "anyOf" in schema:
        if not any(not validate(value, sub, root, root_file, path) for sub in schema["anyOf"]):
            errors.append(f"{path}: matches none of anyOf")
    if "oneOf" in schema:
        hits = sum(1 for sub in schema["oneOf"] if not validate(value, sub, root, root_file, path))
        if hits != 1:
            errors.append(f"{path}: matches {hits} of oneOf, expected 1")
    return errors


def validate_named(value: Any, name: str) -> list[str]:
    schema = load_schema(name)
    file = name if name.endswith(".json") else f"{name}.schema.json"
    return validate(value, schema, schema, file)


def validate_file(path: Path | str, name: str) -> list[str]:
    return [f"{Path(path).name} {err}" for err in validate_named(read_json(path), name)]
