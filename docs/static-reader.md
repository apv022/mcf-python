# Static reader

Python vendors the bundle generated from `../mcf-npm/src/reader`. It loads
normalized data, validates state schema 2, persists pools/shuffles/responses,
implements matching and keyboard ordering, scores automatic work, preserves
manual pending state, evaluates completion, and updates progress. Synchronize
with `cd ../mcf-npm && npm run sync:python-reader`; `test_reader_sync.py`
detects drift. Never edit vendored reader files directly.
