# Architecture and maintenance

The pipeline is package/archive discovery → version detection → version-specific YAML and semantic parsing → typed model → accumulated reference validation → sanitized rich-content rendering → static reader generation → staged replacement and catalog update.

`package.py` owns exact dispatch and the public APIs. `package_reader.py` handles directories and bounded archive extraction. `yaml_profile.py` implements restricted MCF 1.1 YAML. `parser.py` and `lesson.py` retain MCF 1.0; `parser11.py` implements MCF 1.1 package kinds and semantics. `model.py` owns the intermediate representation and structured diagnostics. `render.py` handles Markdown, media, compile-time MathML, sanitization, controls, and page HTML. `compiler.py` emits directory and standalone readers.

MCF packages are untrusted. MCF 1.1 YAML uses a restricted JSON-compatible profile; archives are bounded and reject unsafe entries; authored HTML passes through an allowlist; script and event attributes are removed; URLs use a narrow scheme list; local references are lexically and physically contained; copied files are resolved again; JSON embedded in scripts escapes `<`. Reader code never evaluates authored JavaScript.

Reader CSS and bundled JavaScript are vendored unchanged from the current `mcf-npm` build because they define implementation-specific behavior. Run `python scripts/check_reader_sync.py ../mcf-npm` after reference-reader changes and review deliberate updates. WOFF2 fonts and `katex.min.css` come from KaTeX 0.16.22 under its MIT license.

For local development, clone this repository, create a virtual environment, install it with `python -m pip install -e .`, and add development tools with `python -m pip install -e ".[dev]"`. The package is not published to PyPI yet.

To add an officially standardized activity or question, update the model and parser validation first, add invalid and valid fixtures, then update rendering and the reader data/runtime. Add media syntax in reference extraction, validation, copying, and rendering together. Future MCF versions should use version-keyed parsers rather than unofficial MCF 1.0 fields. Reader-only features belong in the reader and must not be described as source-format conformance.

Compilation is deterministic except for filesystem staging names. JSON uses stable insertion order and readable indentation; HTML is emitted structurally and does not invoke a runtime formatter. Course replacement uses a same-filesystem staging directory and rollback backup. Root catalog files use atomic file replacement. A failure during catalog update can leave the successfully replaced course present but its old catalog record; recompilation repairs this practical cross-file atomicity limitation.

`compile_single_file(input, output)` shares the normal compiler's parser, validator, ordering, renderer, and reader data model. It puts all lesson sections in one document, switches navigation to internal anchors, inlines the reader bundle and styles, and converts local media, cover files, and KaTeX resources to data URLs. It writes through an atomic temporary sibling file, does not update the library catalog, and rejects destinations inside the source package to prevent recursive inclusion.
