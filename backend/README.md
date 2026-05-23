# Backend — Plan 1

FastAPI backend foundation for the ops diagnostic agent: file ingestion, parsing for 10 file types with locator anchors, and an LLM provider layer over Ollama / OpenAI / Groq / OpenAI-compatible. **No mock provider** — every layer runs against a real provider end-to-end.

## Quick start

```bash
make install                            # uv venv + uv pip install -e ".[dev]"
cp backend/.env.example backend/.env    # edit values
make fixtures                           # generates parser test fixtures
make test                               # 58 tests, 3 skip-gated on hosted keys
make dev                                # starts uvicorn on :8000
```

## Test scopes

```bash
make test-unit          # deterministic, in-process (parsers, schemas, config)
make test-integration   # touches real DB / real Ollama / real HTTP
```

## Endpoints

- `GET /health`
- `POST /api/files` — multipart upload, returns `{file_id, parser_status, ...}`.
- `POST /api/files/{file_id}/excerpt` — body `{"locator": {...}}`, returns `{"text": "..."}`.

The excerpt endpoint accepts the structured locator from `app/schemas.py` (PdfLocator, TranscriptLocator, etc.) as a JSON object.

## Providers

Set `LLM_PROVIDER` in `.env` to one of:
- `ollama` — default, requires Ollama running locally
- `openai` — requires `OPENAI_API_KEY`
- `groq` — requires `GROQ_API_KEY`
- `openai_compatible` — requires all three `OPENAI_COMPATIBLE_*` vars

The Ollama provider test uses `OLLAMA_MODEL` from `.env`. Any chat-capable Ollama model that supports `format=json` works (tested with `llama3.2:3b`).

## What this plan does NOT include

Agents, LangGraph parent workflow, Redis checkpointer, Langfuse observability, persistence for `file_summaries` / `intake_bundles` / `blueprints`, Next.js frontend, `make demo`. See Plan 2 (`docs/build_from_scratch_plan.md`).
