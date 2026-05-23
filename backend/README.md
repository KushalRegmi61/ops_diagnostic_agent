# Backend

FastAPI backend for the ops diagnostic agent: file ingestion, parsing for 10 file types with locator anchors, LLM providers (Ollama / OpenAI / Groq / OpenAI-compatible), multi-agent LangGraph parent workflow with Redis-backed checkpointing, and Langfuse observability. **No mock provider** — every layer runs against a real provider end-to-end.

## Quick start

```bash
make install                            # uv venv + uv pip install -e ".[dev]"
cp backend/.env.example backend/.env    # edit values (Langfuse keys, etc.)
make fixtures                           # generates parser test fixtures
make test                               # all tests; integration tests gate on services below
make dev                                # starts uvicorn on :8000
```

## Required services (for integration tests + runs)

- **Ollama** at `OLLAMA_BASE_URL` with the configured model pulled (`llama3.2:3b` works).
- **Redis Stack** at `REDIS_URL` — plain `redis-server` is NOT enough. The LangGraph checkpointer (`langgraph-checkpoint-redis`) requires the RedisJSON and RediSearch modules that ship with Redis Stack.

  ```bash
  # Local install (tarball, no sudo needed):
  wget https://packages.redis.io/redis-stack/redis-stack-server-7.4.0-v3.jammy.x86_64.tar.gz
  tar -xzf redis-stack-server-*.tar.gz
  ./redis-stack-server-7.4.0-v3/bin/redis-stack-server --daemonize yes --port 6379

  # Verify modules:
  redis-cli MODULE LIST  # expect "search" and "ReJSON" entries
  ```

- **Langfuse** (optional but recommended): set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY`. When unset, observability hooks become no-ops.

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

## What is still out of scope

Next.js frontend, `/samples` realistic dataset, Dockerized `make demo` — all live in Plan 3 (`docs/build_from_scratch_plan.md`).
