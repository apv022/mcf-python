"""Bundled canonical JSON Schema validation."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Any

from jsonschema import FormatChecker  # type: ignore[import-untyped]
from jsonschema.validators import validator_for  # type: ignore[import-untyped]
from referencing import Registry, Resource

from .model import ValidationIssue
from .yaml_profile import diagnostic


@lru_cache(maxsize=2)
def _schemas(version: str) -> tuple[dict[str, dict[str, Any]], Registry[Any]]:
    root = files("mcf_compiler").joinpath("schemas", version)
    schemas: dict[str, dict[str, Any]] = {}
    registry: Registry[Any] = Registry()
    for item in root.iterdir():
        if item.name.endswith(".json"):
            schema = json.loads(item.read_text(encoding="utf-8"))
            schemas[item.name] = schema
            resource = Resource.from_contents(schema)
            identifier = schema.get("$id", f"https://mcf.local/{version}/{item.name}")
            registry = registry.with_resource(identifier, resource)
    return schemas, registry


def validate_schema(
    value: Any,
    version: str,
    schema_name: str,
    file: str,
    *,
    code: str = "MCF_SCHEMA_INVALID",
) -> list[ValidationIssue]:
    schemas, registry = _schemas(version)
    schema = schemas[schema_name]
    validator_class = validator_for(schema)
    validator_class.check_schema(schema)
    validator = validator_class(schema, registry=registry, format_checker=FormatChecker())
    return [
        diagnostic(
            code,
            file,
            f"{'/'.join(str(part) for part in error.absolute_path) or '$'}: {error.message}",
        )
        for error in sorted(validator.iter_errors(value), key=lambda item: list(item.path))
    ]
