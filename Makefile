.PHONY: install dev test fixtures

install:
	cd backend && uv venv && uv pip install -e ".[dev]"

dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload

test:
	cd backend && . .venv/bin/activate && pytest -v

fixtures:
	cd backend && . .venv/bin/activate && python tests/fixtures/make_fixtures.py
