# MUI Debug Agent — Frontend

Chat interface for the [MUI Debug Agent](https://github.com/shrivs4/mui-debug-agent): describe a
Material UI bug or paste an error, and the agent answers with a fix grounded in real resolved
GitHub issues and current docs.

**Live demo:** [mui-debug-fe.vercel.app](https://mui-debug-fe.vercel.app/) · **Backend repo:** [shrivs4/mui-debug-agent](https://github.com/shrivs4/mui-debug-agent)

The agent itself — tools, retrieval, memory, and design decisions — is documented in the
[backend README](https://github.com/shrivs4/mui-debug-agent#readme). This repo is the UI layer.

## How it works

```
Browser → /api/ask (Next.js route, server-side) → FastAPI backend on Render → Claude agent
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
- **All request logic lives in one hook** (`hooks/useChat.ts`), so streaming can be added
  later without touching the components.

## Run locally

```bash
npm install
echo "BACKEND_URL=https://mui-debug-agent.onrender.com" > .env.local
npm run dev
```

Open http://localhost:3000. To use a local backend instead, set
`BACKEND_URL=http://127.0.0.1:8000` (no trailing slash).

## Deployment

Deployed on Vercel. The only environment variable is `BACKEND_URL` (server-side; no
`NEXT_PUBLIC_` prefix, so it never reaches the browser).

## Files

| File | Purpose |
|---|---|
| `app/api/ask/route.ts` | Server-side proxy to the backend's `POST /ask` |
| `hooks/useChat.ts` | Messages, loading state, conversation id, send / retry / new chat |
| `app/page.tsx` | Chat page: header, thread, input |
| `components/ChatMessage.tsx` | User, assistant (Markdown) and error messages |
| `components/TypingIndicator.tsx` | Typing dots and the "waking the server" notice |
| `components/EmptyState.tsx` | Clickable example questions |

**Stack:** Next.js 16 (App Router) · React 19 · TypeScript · Tailwind CSS v4 · react-markdown · Vercel

The UI was built with AI assistance (Claude Code), reviewed and corrected by me.