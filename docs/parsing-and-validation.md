# Parsing and validation

`validate_package` opens transport, reads the root manifest, and dispatches exact
`1.0` to `parser.py`, exact `1.1` to `parser11.py`, and rejects every other
version. `yaml_profile.py` enforces the restricted JSON-compatible profile
before schemas and semantic rules. Schema shape, filesystem/reference
semantics, and rendering policy remain separate layers.
