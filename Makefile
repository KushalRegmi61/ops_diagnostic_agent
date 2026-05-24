.PHONY: install dev dev-backend dev-frontend test test-unit test-integration test-frontend fixtures

install:
	cd backend && uv venv && uv pip install -e ".[dev]"
	cd frontend && npm install

dev: dev-backend

dev-backend:
	cd backend && uv run uvicorn app.main:app --reload

dev-frontend:
	cd frontend && npm run dev

test:
	cd backend && uv run pytest -v
	cd frontend && npm run lint
	cd frontend && npm run build

test-unit:
	cd backend && uv run pytest tests/unit -v

test-integration:
	cd backend && uv run pytest tests/integration -v

test-frontend:
	cd frontend && npm run lint
	cd frontend && npm run build

fixtures:
	cd backend && uv run python tests/fixtures/make_fixtures.py
