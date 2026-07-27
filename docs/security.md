# Security

Boundaries include YAML, ZIP, paths, raw HTML, URLs, extensions, state import,
and output containment. Bleach sanitization blocks scripts, handlers, and active
schemes. Remote resources are not fetched by default. Extensions are not
executed. Canonical-path checks prevent package/output escape, and atomic writes
avoid exposing partial targets.
