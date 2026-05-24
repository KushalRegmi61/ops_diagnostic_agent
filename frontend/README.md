# Ops Diagnostic Agent Frontend

Next.js App Router frontend for the Ops Diagnostic Agent. The first screen is
the working diagnostic workspace from Plan 3: upload operational evidence,
start a backend run, watch local progress state, and review the cited
blueprint once the FastAPI service returns it.

## Stack

- Next.js 16 + React 19
- TypeScript with strict mode
- Tailwind CSS v4
- ESLint via `eslint-config-next`
- `lucide-react` for UI icons

## Configuration

Create `frontend/.env.local` when the backend is not running on the default
local URL:

```bash
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

The backend must allow the browser origin with `FRONTEND_CORS_ORIGINS`; the
default backend setting includes `http://localhost:3000`.

## Commands

```bash
npm run dev
npm run lint
npm run build
```

From the repo root, `make dev-frontend` starts the frontend and
`make test-frontend` runs lint plus a production build.
