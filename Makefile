.PHONY: test lint type-check run

# Run unit tests
test:
	PYTHONPATH=. pytest

# Linter (ruff)
lint:
	PYTHONPATH=. ruff check app tests

# Static types (mypy)
type-check:
	PYTHONPATH=. mypy app

# Run the app
run:
	PYTHONPATH=. python main.py