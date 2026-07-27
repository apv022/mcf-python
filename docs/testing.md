# Testing

Run `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`,
`.venv/bin/mypy src`, and `.venv/bin/python -m pytest`. Build with
`.venv/bin/python -m build` and check with `.venv/bin/twine check dist/*`.
The cross-compiler Playwright matrix is `cd ../examplecourses/browser-tests &&
npm test`. A successful compile proves file generation, not learner behavior.
