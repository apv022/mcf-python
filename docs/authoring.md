# Authoring MCF 1.0

Use the published MCF 1.0 specification as the normative reference. Required manifest fields are `mcf: '1.0'`, `id`, `title`, `language`, and a non-empty ordered `chapters` list. Optional fields are `description`, `authors`, `license`, `version`, and `cover`. Each chapter requires `id`, `title`, and a non-empty ordered `lessons` list. Lessons require `id`, `title`, and at least one closed activity; optional lesson fields are `description`, `authors`, and `license`.

Identifiers match `[a-z][a-z0-9._-]*`. Chapter and distinct lesson IDs are unique in a course; activity and question IDs are unique in a lesson; option IDs are unique in a question.

Activities require `type` and `id`; `title` is optional. `passing_score` is an assessment-only number from 0 to 1. `randomize` and positive `question_pool_size` are practice/assessment-only, and a pool cannot exceed its activity question count.

All questions require string `id`, `type`, and `prompt`. `points` is a finite non-negative number (default 1), `required` is boolean (default true), and `hint`/`explanation` are optional rich content. Multiple choice requires one answer option ID; multiple select requires a non-empty distinct list; true/false requires YAML boolean; numeric requires a finite number and optional non-negative absolute `tolerance`; short answer requires a string; essay must not declare `answer`.

Essay `minimum_words`, `minimum_sentences`, and `minimum_keywords` are positive integers. `keywords` is a non-empty distinct list of non-empty strings, and the minimum cannot exceed its length. With keywords but no explicit minimum, the reader requires all listed concepts. Criteria establish completion, never correctness.

Content outside activity containers is invalid except whitespace and HTML comments. Rich local paths resolve from the containing lesson. All package paths use `/`, cannot traverse above the course root, cannot escape through symlinks, and must exist. HTTP(S) references are valid but need a network. Raw HTML is permitted only through the sanitizer allowlist.

The reference repositories organize examples by purpose: minimal demonstrates the smallest useful package; showcase covers every syntax and reader feature; calculus is a realistic multi-chapter course. They are authoring fixtures, not files shipped in the Python wheel.
