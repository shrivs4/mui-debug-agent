# MUI Debug Agent — Frontend

Chat interface for the MUI Debug Agent: describe a Material UI bug or paste an error, and the
agent answers with a fix grounded in real resolved GitHub issues and current docs.

**Live demo:** [mui-debug-fe.vercel.app](https://mui-debug-fe.vercel.app/)

This folder is the UI layer of a monorepo. The agent itself — tools, retrieval, memory, and
design decisions — is documented in the [main README](../README.md), and its code is in
[`../backend`](../backend).

## How it works

```
Browser → /api/ask (Next.js route, server-side) → FastAPI backend → Claude agent
```

The browser never calls the backend directly. The Next.js route handler forwards each request
server-side, so there's no CORS setup, the backend URL stays out of the client bundle, and there
is one place to add auth or rate limiting later.

## Frontend decisions

- **The frontend owns the conversation.** A `conversation_id` is generated with
  `crypto.randomUUID()` when the page loads and sent with every question; the backend keys its
  memory on it. **New chat** generates a fresh id, which starts a clean history on the backend.
- **Built for a slow backend.** The backend runs on Render's free tier (30–50 s cold start) and
  the agent makes tool calls, so the route allows up to 60 s (`maxDuration`), and after 8 s the
  UI tells the user the server is waking up.
- **No stale answers after New chat.** Clicking New chat aborts the in-flight request
  (`AbortController`) and ignores its response, so an old answer can't land in the new thread.
  (Aborting only cancels the browser side — the backend still finishes and writes to the old,
  now-unused conversation.)
- **Errors are visible and retryable.** Failures show in the thread with a Retry button that
  re-sends without duplicating the user's message. If the platform returns a non-JSON timeout
  page, the UI says the server took too long rather than showing a generic network error.
- **Fails loudly when misconfigured.** If `BACKEND_URL` is missing, the route returns a clear
  500 ("BACKEND_URL is not configured") instead of guessing a URL.
- **All request logic lives in one hook** (`hooks/useChat.ts`), so streaming can be added
  later without touching the components.

## Run locally

**Whole stack (recommended):** from the repo root, `docker compose up --build` — see the
[main README](../README.md#quick-start-full-stack-docker).

**Frontend only, with the dev server:**

```bash
cd frontend
npm install
echo "BACKEND_URL=http://localhost:8000" > .env.local
npm run dev
```

Open http://localhost:3000. `BACKEND_URL` depends on where the frontend runs (no trailing
slash):

| Frontend runs… | `BACKEND_URL` |
|---|---|
| On your machine (`npm run dev`), backend local | `http://localhost:8000` |
| In Docker Compose | `http://backend:8000` (set in `docker-compose.yml`) |
| On Vercel | the deployed backend's URL |

Inside a container, `localhost` means that container itself, which is why Compose uses the
service name instead.

## Docker image

`Dockerfile` is a three-stage build:

1. **deps** — `npm ci` from the lockfile only, so this layer is cached until dependencies change.
2. **builder** — copies `node_modules` from `deps`, adds the source, runs `npm run build`.
3. **runner** — a fresh `node:20-alpine` that copies only the build output:
   `.next/standalone` (from `output: "standalone"` in `next.config.ts`), `.next/static` and
   `public/`, then runs `node server.js` with `HOSTNAME=0.0.0.0`.

Only the last stage ships: the builder image is **1.16 GB**, the final image **289 MB**.
Build tools and source code never reach the runtime image. `.dockerignore` keeps local
`node_modules`, `.next` and every `.env*` file out of the build context.

## Deployment

Deployed on Vercel from this monorepo with *Root Directory* set to `frontend`. Vercel builds
Next.js its own way, so the Dockerfile and `output: "standalone"` don't affect it. The only
environment variable is `BACKEND_URL` (server-side; no `NEXT_PUBLIC_` prefix, so it never
reaches the browser).

## Files

| File | Purpose |
|---|---|
| `app/api/ask/route.ts` | Server-side proxy to the backend's `POST /ask` |
| `hooks/useChat.ts` | Messages, loading state, conversation id, send / retry / new chat |
| `app/page.tsx` | Chat page: header, thread, input |
| `components/ChatMessage.tsx` | User, assistant (Markdown) and error messages |
| `components/TypingIndicator.tsx` | Typing dots and the "waking the server" notice |
| `components/EmptyState.tsx` | Clickable example questions |
| `Dockerfile` / `.dockerignore` | Multi-stage production image for local and Compose use |

**Stack:** Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · react-markdown ·
Docker · Vercel

The UI was built with AI assistance (Claude Code), reviewed and corrected by me.