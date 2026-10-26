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
server-side, so there's no CORS setup and the backend URL and API key stay out of the client
bundle. The route adds the shared `X-API-Key`, forwards the user's real IP as `X-Client-IP`
(for the backend's rate limit), forwards the browser's abort signal, and passes the backend's
NDJSON stream straight through instead of waiting for the whole body.

## Frontend decisions

- **The frontend owns the conversation.** A `conversation_id` is generated with
  `crypto.randomUUID()` when the page loads and sent with every question; the backend keys its
  memory on it. **New chat** generates a fresh id, which starts a clean history on the backend.
- **Built for a slow backend.** The backend runs on Render's free tier (30–50 s cold start) and
  the agent makes tool calls, so the route allows up to 60 s (`maxDuration`), and after 8 s the
  UI tells the user the server is waking up.
- **Streaming.** `useChat` reads the response with `getReader()` + `TextDecoder` and buffers
  it, because network chunks aren't lines: only complete NDJSON lines are parsed, and the last
  partial line waits for the next chunk. `status` events show in the typing indicator while
  tools run; the assistant bubble appears on the first `text` event and is updated by id with
  functional state updates (deltas arrive faster than React re-renders).
- **Smooth reveal.** `useSmoothText` reveals streamed text with `requestAnimationFrame` at an
  adaptive pace, so bursts don't look jumpy; it respects `prefers-reduced-motion`.
- **No stale answers after New chat.** Clicking New chat aborts the in-flight request
  (`AbortController`). The route forwards the abort, so the backend stops the agent and closes
  the Claude stream as well.
- **Errors are visible and retryable.** Failures show in the thread with a Retry button that
  re-sends without duplicating the user's message. If the platform returns a non-JSON timeout
  page, the UI says the server took too long rather than showing a generic network error.
- **Fails loudly when misconfigured.** If `BACKEND_URL` or `BACKEND_API_KEY` is missing, the
  route returns a clear 500 instead of guessing.
- **All request logic lives in one hook** (`hooks/useChat.ts`) — which is why streaming could be
  added later without touching the components. It still accepts the old JSON response, so the
  frontend can be deployed before the backend.

## Run locally

**Whole stack (recommended):** from the repo root, `docker compose up --build` — see the
[main README](../README.md#quick-start-full-stack-docker).

**Frontend only, with the dev server:**

```bash
cd frontend
npm install
echo "BACKEND_URL=http://localhost:8000" > .env.local
echo "BACKEND_API_KEY=<same value as in backend/.env>" >> .env.local
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
environment variables are `BACKEND_URL` and `BACKEND_API_KEY` — both server-side. Neither has
the `NEXT_PUBLIC_` prefix: Next.js inlines `NEXT_PUBLIC_*` variables into the browser bundle at
build time, so the prefix is what decides who can see a variable.

## Files

| File | Purpose |
|---|---|
| `app/api/ask/route.ts` | Server-side proxy to the backend's `POST /ask` |
| `hooks/useChat.ts` | Messages, streaming NDJSON reader, status, conversation id, send / retry / new chat |
| `hooks/useSmoothText.ts` | Adaptive-speed reveal of streamed text |
| `app/page.tsx` | Chat page: header, thread, input |
| `components/ChatMessage.tsx` | User, assistant (Markdown) and error messages |
| `components/TypingIndicator.tsx` | Typing dots, the agent's current status, and the "waking the server" notice |
| `components/EmptyState.tsx` | Clickable example questions |
| `Dockerfile` / `.dockerignore` | Multi-stage production image for local and Compose use |

**Stack:** Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · react-markdown ·
Docker · Vercel

The UI was built with AI assistance (Claude Code), reviewed and corrected by me.