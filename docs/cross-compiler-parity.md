# Cross-compiler parity

| Responsibility | Python | TypeScript |
|---|---|---|
| Dispatch | `package.py` | `src/package.ts` |
| Package reader | `package_reader.py` | `src/package-reader.ts` |
| 1.0/1.1 parsers | `parser.py`, `parser11.py` | `parser.ts`, `parser11.ts` |
| Model | `model.py` | `model.ts` |
| Compiler | `compiler.py` | `compiler.ts` |
| Renderer | `render.py` | `render.ts` |
| Browser | generated `assets/reader` | canonical `src/reader` |

Canonical validity/principal diagnostics and normalized data are compared in
pytest. The shared Playwright suite compares learner behavior in four outputs.
