"""The restricted, deterministic YAML profile required by MCF 1.1."""

from __future__ import annotations

import math
import re
from copy import deepcopy
from typing import Any

import yaml

from .model import ValidationIssue


class _McfLoader(yaml.SafeLoader):
    pass


# PyYAML defaults to YAML 1.1 booleans. MCF uses the JSON/YAML-core spellings.
_McfLoader.yaml_implicit_resolvers = deepcopy(yaml.SafeLoader.yaml_implicit_resolvers)
for first, resolvers in list(_McfLoader.yaml_implicit_resolvers.items()):
    _McfLoader.yaml_implicit_resolvers[first] = [
        item for item in resolvers if item[0] != "tag:yaml.org,2002:bool"
    ]
_McfLoader.add_implicit_resolver(
    "tag:yaml.org,2002:bool", re.compile(r"^(?:true|false)$", re.IGNORECASE), list("tTfF")
)  # type: ignore[no-untyped-call]


def diagnostic(
    code: str,
    file: str,
    message: str,
    severity: str = "error",
    object_id: str | None = None,
    location: dict[str, int] | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        file=file,
        message=message,
        severity=severity,  # type: ignore[arg-type]
        code=code,
        object_id=object_id,
        location=location,
    )


def _construct_mapping(
    loader: _McfLoader, node: yaml.MappingNode, deep: bool = False
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        if not isinstance(key, str):
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                "MCF YAML mapping keys must be strings",
                key_node.start_mark,
            )
        if key == "<<" or key in result:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"duplicate or merge key {key!r}",
                key_node.start_mark,
            )
        result[key] = loader.construct_object(value_node, deep=deep)
    return result


_McfLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct_mapping)


def parse_mcf_yaml(
    source: str,
    file: str,
    issues: list[ValidationIssue],
    code: str = "MCF_YAML_INVALID",
) -> Any:
    if source.startswith("\ufeff"):
        issues.append(diagnostic(code, file, "UTF-8 byte-order marks are not allowed."))
        return {}
    try:
        for token in yaml.scan(source, Loader=_McfLoader):
            if isinstance(token, (yaml.AnchorToken, yaml.AliasToken, yaml.TagToken)):
                raise yaml.YAMLError("Tags, anchors, and aliases are not permitted.")
        nodes = list(yaml.compose_all(source, Loader=_McfLoader))
        if len(nodes) != 1:
            raise yaml.YAMLError("MCF YAML must contain exactly one document.")
        node = nodes[0]
        if node is not None:
            stack = [node]
            while stack:
                current = stack.pop()
                if isinstance(current, yaml.MappingNode):
                    for key, value in current.value:
                        stack.extend((key, value))
                elif isinstance(current, yaml.SequenceNode):
                    stack.extend(current.value)
                elif current.tag not in {
                    "tag:yaml.org,2002:null",
                    "tag:yaml.org,2002:bool",
                    "tag:yaml.org,2002:int",
                    "tag:yaml.org,2002:float",
                    "tag:yaml.org,2002:str",
                }:
                    raise yaml.YAMLError("Custom YAML tags are not permitted.")
        value = yaml.load(source, Loader=_McfLoader)
    except yaml.YAMLError as error:
        message = str(error)
        duplicate = "duplicate or merge key" in message
        issues.append(diagnostic("MCF_YAML_DUPLICATE_KEY" if duplicate else code, file, message))
        return {}

    def invalid(item: Any) -> bool:
        if isinstance(item, float):
            return not math.isfinite(item)
        if isinstance(item, list):
            return any(invalid(child) for child in item)
        if isinstance(item, dict):
            return any(not isinstance(key, str) or invalid(child) for key, child in item.items())
        return not isinstance(item, (str, int, bool, type(None)))

    if invalid(value):
        issues.append(
            diagnostic(code, file, "MCF YAML permits only finite JSON-compatible values.")
        )
        return {}
    return value
