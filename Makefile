.PHONY: install dev test test-unit test-integration fixtures

install:
	cd backend && uv venv && uv pip install -e ".[dev]"

dev:
	cd backend && . .venv/bin/activate && uvicorn app.main:app --reload

test:
	cd backend && . .venv/bin/activate && pytest -v

test-unit:
	cd backend && . .venv/bin/activate && pytest tests/unit -v

test-integration:
	cd backend && . .venv/bin/activate && pytest tests/integration -v

fixtures:
	cd backend && . .venv/bin/activate && python tests/fixtures/make_fixtures.py
