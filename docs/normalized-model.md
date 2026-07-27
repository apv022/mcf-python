# Normalized model

`model.py` defines typed dataclasses for both versions. Authored version, kind,
identity, metadata, order, activities, questions, scoring, relationships,
assets, rubrics, completion, dependencies, and extensions are retained.
Module/lesson compilation uses a private course-shaped adapter whose
`_source_kind` is emitted as the original public kind.
