# Architecture and maintenance

The pipeline is package discovery → YAML/frontmatter parsing → typed model → accumulated semantic/reference validation → sanitized rich-content rendering → static reader generation → staged replacement and catalog update.

`model.py` owns the source intermediate representation and diagnostics. `yamlio.py` performs safe YAML loading and scalar checks. `paths.py` centralizes portable path, URL, existence, and real-path containment checks. `lesson.py` parses frontmatter, activity boundaries, question fences, and type-specific fields. `parser.py` follows declared package order and validates cross-file uniqueness and rich-content references. `render.py` handles Markdown, media, compile-time MathML, sanitization, controls, and page HTML. `compiler.py` emits course data/pages/assets, maintains the library, and assembles standalone HTML. `cli.py` only handles arguments, output streams, and status codes.

MCF packages are untrusted. YAML uses `safe_load`; authored HTML passes through an allowlist; script and event attributes are removed; URLs use a narrow scheme list; local references are lexically and physically contained; copied files are resolved again; JSON embedded in scripts escapes `<`. Reader code never evaluates authored JavaScript.

Reader CSS and bundled JavaScript are vendored unchanged from `mcf-npm` 1.0.0 because they define implementation-specific behavior. Run `python scripts/check_reader_sync.py ../mcf-npm` after reference-reader changes, review them, copy deliberate updates, and update the documented compatibility version. WOFF2 fonts and `katex.min.css` come from KaTeX 0.16.22 under its MIT license.

For local development, clone this repository, create a virtual environment, install it with `python -m pip install -e .`, and add development tools with `python -m pip install -e ".[dev]"`. The package is not published to PyPI yet.

To add an officially standardized activity or question, update the model and parser validation first, add invalid and valid fixtures, then update rendering and the reader data/runtime. Add media syntax in reference extraction, validation, copying, and rendering together. Future MCF versions should use version-keyed parsers rather than unofficial MCF 1.0 fields. Reader-only features belong in the reader and must not be described as source-format conformance.

Compilation is deterministic except for filesystem staging names. JSON uses stable insertion order and readable indentation; HTML is emitted structurally and does not invoke a runtime formatter. Course replacement uses a same-filesystem staging directory and rollback backup. Root catalog files use atomic file replacement. A failure during catalog update can leave the successfully replaced course present but its old catalog record; recompilation repairs this practical cross-file atomicity limitation.

`compile_single_file(input, output)` shares the normal compiler's parser, validator, ordering, renderer, and reader data model. It puts all lesson sections in one document, switches navigation to internal anchors, inlines the reader bundle and styles, and converts local media, cover files, and KaTeX resources to data URLs. It writes through an atomic temporary sibling file, does not update the library catalog, and rejects destinations inside the source package to prevent recursive inclusion.
