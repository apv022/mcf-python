# mcf-compiler

`mcf-compiler` is a typed Python validator and compiler for [Modular Curriculum Format (MCF) 1.0 and 1.1](https://github.com/apv022/mcf-spec). It performs exact declared-version dispatch, reads directory and `.mcf.zip` packages, and produces the same static, offline-first course library used by the reference `mcf-npm` compiler.

MCF is the standardized source format. Generated HTML, navigation, grading presentation, browser storage, progress export/import, and the completion badge are reader implementation features and do not extend the MCF specification.

## Install and use from a clone

Python 3.11 or newer is required to compile. The package is not published to PyPI yet; install it from a cloned repository. Learners only need a browser.

```bash
git clone https://github.com/apv022/mcf-python.git
cd mcf-python

python -m venv .venv
source .venv/bin/activate
# Windows PowerShell:
# .venv\Scripts\Activate.ps1

python -m pip install --upgrade pip
python -m pip install -e .
```

Use the installed command:

```bash
mcf --help
mcf validate /path/to/package --format json
mcf inspect /path/to/package
mcf capabilities --format yaml
mcf compile /path/to/course --output ./courses
mcf compile /path/to/course --single-file ./exports/course.html
```

The module form is an equivalent fallback:

```bash
python -m mcf_compiler --help
python -m mcf_compiler validate /path/to/course
python -m mcf_compiler compile /path/to/course --output ./courses
python -m mcf_compiler compile /path/to/course --single-file ./exports/course.html
```

The repository includes `examples/minimal` for MCF 1.0 and
`examples/minimal-1.1` for MCF 1.1.

`validate`, `inspect`, and `compile` accept `--expected-version 1.0|1.1`, repeatable `--package` dependency inputs, and `--allow-remote`. Diagnostics support text or JSON. Exit status 2 is a validation failure, 3 is a version mismatch, 4 is an unsupported required extension, and 5 is a security-policy rejection.

`--output` is the normal multi-file library mode. `--single-file` creates one standalone HTML document containing the reader UI, course data, lessons, styles, scripts, KaTeX resources, and local media. The destination parent is created when needed, and recompilation atomically replaces the destination. Validation runs before output is written, and all output must be outside the source package.

Standalone files open directly as local files without Python, Node.js, a server, sibling files, or an internet connection for local course content. Explicitly remote URLs and YouTube still require the network; YouTube retains the direct-file fallback behavior.

For development dependencies, run:

```bash
python -m pip install -e ".[dev]"
```

Validation failures are accumulated and written to stderr; both validation and compilation return a nonzero status. Open the generated `courses/index.html` directly. No Node.js is required. Current Chromium-based browsers and Safari provide the best `file://` experience; Firefox may require `python -m http.server --directory courses`. Local assets and the UI work offline. Remote media still requires a connection, and YouTube embeds require HTTP, with a direct-file fallback link supplied by the reader.

## Course source

```text
course/
├── manifest.yaml
├── assets/                         # optional
└── chapters/
    └── introduction/
        ├── chapter.yaml
        └── lessons/
            └── welcome.mcf
```

The manifest declares chapter order, and each `chapter.yaml` declares lesson order. Filenames never determine course order. Paths use forward slashes, remain under the course root after symlinks are resolved, and local references must exist.

```yaml
# manifest.yaml
mcf: '1.1'
kind: course
id: example-course
title: Example Course
language: en
version: '1.1.0'
chapters:
  - source: chapters/introduction
```

```yaml
# chapters/introduction/chapter.yaml
id: introduction
title: Introduction
lessons:
  - lessons/welcome.mcf
```

Lessons are Markdown with YAML frontmatter and one or more activity containers:

````markdown
---
id: welcome
title: Welcome
---

:::mcf-activity
type: practice
id: first-check
title: First check
:::

```mcf-question
id: q1
type: multiple_choice
prompt: Which format is this course using?
options:
  - id: mcf
    text: MCF
  - id: other
    text: Something else
answer: mcf
hint: Read the heading.
explanation: This is an MCF course.
```

:::mcf-end
````

MCF 1.1 supports `course`, `module`, `lesson`, `question_bank`, and `asset_collection` packages. Activity types are `notes`, `practice`, `assessment`, and `assignment`; question types add `open_response`, `matching`, and `ordering` to the six 1.0 types. It also defines evaluation modes, submissions, rubrics, completion expressions, relationships, declared assets, question-bank references, and namespaced extensions. MCF 1.0 packages retain their original parser and semantics.

Rich content supports CommonMark, tables, fenced code, links, images, inline `$x$` and display `$$x$$` math, plus audio and video directives:

```markdown
![Graph](../../../assets/images/graph.svg)
@[audio](../../../assets/audio/example.mp3 "Description")
@[video](../../../assets/video/example.mp4 "Description")
@[video](youtube:VIDEO_ID "Online video")
```

See [Authoring](docs/authoring.md) for field rules, [Architecture](docs/architecture.md) for module boundaries and security, and the [1.1.0 migration notes](docs/migration-1.1.md) for API compatibility details. The upstream specification remains normative.

## Generated output

```text
courses/
├── index.html
├── styles.css
├── library.js
├── courses.json
└── example-course/
    ├── index.html
    ├── styles.css
    ├── player.js
    ├── course.json
    ├── katex/
    ├── lessons/
    └── assets/
```

Course and catalog data are emitted as readable JSON and embedded in ordinary scripts for direct-file operation. Compilation uses a staging directory, replaces only the matching course ID, removes stale files from that course, and preserves other library entries.

The programmatic standalone API is also available:

```python
from mcf_compiler import compile_single_file

compile_single_file("./my-course", "./exports/my-course.html")
```

## Compatibility and limitations

The browser JavaScript and CSS are copied unchanged from the current `mcf-npm` reference. `scripts/check_reader_sync.py` detects divergence against a local reference checkout. The Python renderer produces the same reader data shape, data attributes, navigation, media markup, storage identifiers, and output paths.

MCF 1.1 YAML is restricted to finite JSON-compatible values with string keys and no duplicate keys, tags, anchors, aliases, merge keys, or byte-order marks. Archives reject traversal, duplicate/encrypted/special entries and enforce limits of 4,096 entries, 64 MiB per entry, 512 MiB total expanded bytes, and a 200:1 compression ratio. Remote resources are never fetched during ordinary validation or compilation.

Capability declarations intentionally claim no formal conformance classes until every canonical diagnostic trigger and semantic class is implemented. Run `mcf capabilities` for the exact supported versions, package kinds, question types, features, extensions, and limits.

Markdown is generated with `markdown-it-py` CommonMark plus tables and sanitized with Bleach. Math is converted to accessible MathML at compile time and wrapped in KaTeX-compatible `katex`/`katex-display` classes. This is visually browser-native and handles malformed expressions without aborting compilation, but its inner math markup is intentionally not byte-identical to Node KaTeX HTML. No Node runtime or CDN is required.

Raw authored HTML is sanitized. Scripts, event handlers, unsafe protocols, and unsafe embedded content are removed. Authored JavaScript is never evaluated. YouTube is the only provider-style remote video embed; other HTTP(S) media use native media elements.

## Smoke test

```bash
python -m pip install -e ".[dev]"
ruff check .
mypy src
pytest
```

Formatting and compatibility checks:

```bash
ruff format --check .
python scripts/parity_check.py
python scripts/check_reader_sync.py /path/to/mcf-npm
```

The compiler and reader are MIT licensed. Course content retains the license declared by its package.
