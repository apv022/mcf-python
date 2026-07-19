# mcf-compiler

`mcf-compiler` is a typed Python compiler for [Modular Curriculum Format (MCF) 1.0](https://github.com/apv022/MCF-Specification). It validates a human-readable course package and produces the same general static, offline-first course library used by the reference `mcf-npm` compiler.

MCF is the standardized source format. Generated HTML, navigation, grading presentation, browser storage, progress export/import, and the completion badge are reader implementation features and do not extend the MCF specification.

## Install and use

Python 3.11 or newer is required to compile. Learners only need a browser.

```bash
python -m pip install mcf-compiler
mcf validate ./my-course
mcf compile ./my-course --output ./courses
```

For repository development:

```bash
python -m pip install -e '.[dev]'
python -m mcf_compiler validate /path/to/course
python -m mcf_compiler compile /path/to/course --output ./courses
```

Validation failures are accumulated and written to stderr; both validation and compilation return a nonzero status. Open `courses/index.html` directly. Current Chromium-based browsers and Safari provide the best `file://` experience; Firefox may require `python -m http.server --directory courses`. Local assets and the UI work offline. Remote media still requires a connection, and YouTube embeds require HTTP, with a direct-file fallback link supplied by the reader.

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
mcf: '1.0'
id: example-course
title: Example Course
language: en
version: '1.0.0'
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

MCF 1.0 activity types are `notes`, `practice`, and `assessment`. Question types are `multiple_choice`, `multiple_select`, `true_false`, `numeric`, `short_answer`, and `essay`. Practice and assessment support `randomize` and `question_pool_size`; assessments additionally support `passing_score`. Essays may require minimum words, sentences, and keyword coverage, but are never objectively graded.

Rich content supports CommonMark, tables, fenced code, links, images, inline `$x$` and display `$$x$$` math, plus audio and video directives:

```markdown
![Graph](../../../assets/images/graph.svg)
@[audio](../../../assets/audio/example.mp3 "Description")
@[video](../../../assets/video/example.mp4 "Description")
@[video](youtube:VIDEO_ID "Online video")
```

See [Authoring](docs/authoring.md) for complete field rules and [Architecture](docs/architecture.md) for module boundaries, security, reader synchronization, and extension points. The upstream specification remains normative.

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

## Compatibility and limitations

The browser JavaScript and CSS are copied unchanged from `mcf-npm` 1.0.0. `scripts/check_reader_sync.py` detects divergence against a local reference checkout. The Python renderer produces the same reader data shape, data attributes, navigation, media markup, storage identifiers, and output paths.

Markdown is generated with `markdown-it-py` CommonMark plus tables and sanitized with Bleach. Math is converted to accessible MathML at compile time and wrapped in KaTeX-compatible `katex`/`katex-display` classes. This is visually browser-native and handles malformed expressions without aborting compilation, but its inner math markup is intentionally not byte-identical to Node KaTeX HTML. No Node runtime or CDN is required.

Raw authored HTML is sanitized. Scripts, event handlers, unsafe protocols, and unsafe embedded content are removed. Authored JavaScript is never evaluated. YouTube is the only provider-style remote video embed; other HTTP(S) media use native media elements.

## Development and release

```bash
ruff format --check .
ruff check .
mypy src
pytest
python scripts/parity_check.py
python -m build
python -m twine check dist/*
python scripts/check_reader_sync.py /path/to/mcf-npm
```

Before release, compile the minimal, calculus, and showcase examples from the reference repositories, inspect `tar -tf dist/*.tar.gz` and `unzip -l dist/*.whl`, then publish with `python -m twine upload dist/*`. Build artifacts, caches, tests, examples, and local output libraries are excluded from distributions; runtime reader assets, KaTeX CSS, and WOFF2 fonts are included intentionally.

The compiler and reader are MIT licensed. Course content retains the license declared by its package.
