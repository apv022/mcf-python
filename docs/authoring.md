# Authoring MCF 1.0 and 1.1

Use the published specification as the normative reference. MCF 1.0 course manifests require `mcf: '1.0'`, `id`, `title`, `language`, and ordered `chapters`. MCF 1.1 additionally requires `kind` and supports course, module, lesson, question-bank, and asset-collection packages.

Identifiers match `[a-z][a-z0-9._-]*`. Chapter and distinct lesson IDs are unique in a course; activity and question IDs are unique in a lesson; option IDs are unique in a question.

Activities require `type` and `id`; `title` is optional. MCF 1.1 adds assignments, explicit evaluation modes, submission rules, rubrics, and reusable question references. `passing_score` is assessment-only. A positive question pool cannot exceed its available questions and references.

All questions require string `id`, `type`, and `prompt`. `points` is a finite non-negative number (default 1), `required` is boolean (default true), and `hint`/`explanation` are optional rich content. Multiple choice requires one answer option ID; multiple select requires a non-empty distinct list; true/false requires YAML boolean; numeric requires a finite number and optional non-negative absolute `tolerance`; short answer requires a string; essay must not declare `answer`.

Essay `minimum_words`, `minimum_sentences`, and `minimum_keywords` are positive integers. `keywords` is a non-empty distinct list of non-empty strings, and the minimum cannot exceed its length. With keywords but no explicit minimum, the reader requires all listed concepts. Criteria establish completion, never correctness.

Content outside activity containers is invalid except whitespace and HTML comments. Rich local paths resolve from the containing lesson. All package paths use `/`, cannot traverse above the course root, cannot escape through symlinks, and must exist. HTTP(S) references are valid but need a network. Raw HTML is permitted only through the sanitizer allowlist.

The reference repositories organize examples by purpose: minimal demonstrates the smallest useful package; showcase covers every syntax and reader feature; calculus is a realistic multi-chapter course. They are authoring fixtures, not files shipped in the Python wheel.
