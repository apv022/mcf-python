# Migrating Python integrations to 1.1.0

Existing `parse_course`, `compile_course`, and `compile_single_file` calls remain
valid. They now detect the exact declared source version and accept an optional
`ParseOptions` argument. `parse_course` rejects non-course MCF 1.1 packages.

New integrations should use:

```python
from mcf_compiler import ParseOptions, parse_package, validate_package

result = validate_package(path, ParseOptions(expected_version="1.1"))
if result.valid:
    package = parse_package(path)
```

Diagnostics are now structured `ValidationIssue` values with `code`,
`severity`, `file`, optional `location`, and optional `object_id`. Their string
form changed from the legacy multi-line message to
`file: CODE: message`. Code that matched complete exception strings should use
`ValidationError.issues` and diagnostic codes instead.

The normalized course model now exposes `mcf`, `kind`, `source_type`,
`diagnostics`, relationships, assets, rubrics, extensions, and metadata.
Activities and questions expose the MCF 1.1 evaluation and type-specific fields.
The legacy fields and compiler result types remain available.

Unlike the TypeScript API, Python uses snake_case option names and
`parse_package_set(packages, options)` rather than an object containing a
`packages` property. CLI flag names and exit-code meanings match; the installed
command remains `mcf`.

The implementation package version is now 1.1.0. That number describes this
Python release and is not a declaration that every input is MCF 1.1; valid MCF
1.0 sources continue to be processed under their original rules.
