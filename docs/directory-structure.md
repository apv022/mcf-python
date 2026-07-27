# Repository structure

```text
pyproject.toml                    packaging, dependencies, quality-tool config
src/mcf_compiler/cli.py           CLI adapter
src/mcf_compiler/package.py       version/package-set dispatch
src/mcf_compiler/package_reader.py secure directory/ZIP boundary
src/mcf_compiler/parser.py        MCF 1.0 parser
src/mcf_compiler/parser11.py      MCF 1.1 parser and semantics
src/mcf_compiler/yaml_profile.py  restricted YAML
src/mcf_compiler/schema.py        vendored schema registry
src/mcf_compiler/model.py         normalized dataclasses
src/mcf_compiler/render.py        sanitized HTML controls
src/mcf_compiler/compiler.py      tree and one-file output
src/mcf_compiler/schemas/         generated/vendored spec schemas; do not edit
src/mcf_compiler/assets/reader/   generated Node browser runtime; do not edit
src/mcf_compiler/assets/katex/    packaged offline math resources
tests/                            unit, conformance, parity, packaging tests
docs/                             maintainer documentation
```

The editable canonical browser sources are in `../mcf-npm/src/reader`.
