# MUI Debug Agent

An AI agent that debugs Material UI (MUI) problems. Describe a bug or paste an error, and it
finds how similar issues were actually resolved and returns a concrete fix.

**Live demo:** [mui-debug-fe.vercel.app](https://mui-debug-fe.vercel.app/)

> The backend runs on Render's free tier and sleeps when idle, so the first request after a
> quiet period can take up to a minute.

## Repository layout

This is a monorepo: the agent backend and the chat UI live side by side and run together with
one command.

```
.
├── backend/              FastAPI service + Claude tool-use agent (deployed on Render)
├── frontend/             Next.js chat UI (deployed on Vercel) — see frontend/README.md
└── docker-compose.yml    Runs the whole stack locally
```

## Quick start (full stack, Docker)

Requires Docker. Create `backend/.env` with three API keys (no quotes around values):

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
TAVILY_API_KEY=...
```

Then, from the repo root:

```bash
docker compose up --build
```

Open http://localhost:3000. Compose builds both images, starts both containers on a shared
network, and points the frontend at the backend by service name (`http://backend:8000`).
Logs from both services stream into the same terminal.

## What it does

The agent has two tools, and Claude decides which one to call for each question:

- **`search_issues`** — searches **201 closed MUI GitHub issues**. I pulled 300 closed issues
  and kept the 201 that have at least one human (non-bot) comment, so every match comes with
  discussion of how it was handled. Each issue is embedded with OpenAI and stored in Chroma,
  so the search matches **by meaning**, not keywords: a paraphrased description of a bug still
  finds the original issue.
- **`search_web`** — searches the live web (via Tavily) for current MUI docs and recent fixes.
  It acts as a fallback when the issue database has nothing relevant, and as a researcher when
  the resolution found is only a link to a pull request and needs more detail.

Conversations have memory: follow-up questions ("what file should I change?") are answered in
context, and each conversation's history is kept separate.

## Architecture

```
User
 → Next.js frontend
 → Next.js proxy route (/api/ask)
 → FastAPI service (POST /ask)
 → Claude tool-use loop ⇄ search_issues (OpenAI embeddings + Chroma)
                         ⇄ search_web (Tavily)
 → answer (Markdown) back to the user
```

Claude reads the tool descriptions and chooses which tool to call (or none, for general
questions). The loop runs until Claude stops requesting tools, with a cap of 10 rounds.

## Key design decisions

**1. Embed the problem, carry the fix.**
Each issue is stored as one document: title + body + human comments. The main reason: when an
issue matches, Claude receives the problem *and* how it was resolved in a single retrieval.
Including the comments may also help retrieval when a user's wording overlaps with the fix
discussion — or it may dilute the match with off-topic thread content. That trade-off isn't
measured yet; a retrieval eval comparing both approaches is planned.

**2. OpenAI embeddings; Chroma only stores and searches.**
Chroma's built-in default embeds with a local model, which adds a heavy ML runtime to the
container. Embedding through the API (`text-embedding-3-small`) keeps the service at about
150 MB of the free tier's 512 MB. The same model is used at build time and query time (shared
`embed_util.py`) — mixing models would break retrieval.

**3. Truncate long issues at 8,000 characters.**
Embedding failed on issues over the model's 8,192-token limit. Before changing anything I
measured: 8 of 201 issues (~4%) exceeded 8,000 characters. Truncating keeps the title and the
start of the body — the part that describes the problem — and drops trailing discussion.
Proper chunking is the real fix.

**4. Build the index once and ship it with the code.**
Embedding 201 issues means 201 paid API calls, and the data is static, so `embed.py` is run
manually once and the resulting `chroma_db/` (6.8 MB) is committed. The server only loads it.
Freshness is handled separately: `search_web` covers anything newer than the snapshot.

**5. Memory per conversation, not per server.**
Each request carries a `conversation_id`, and history is stored in
`histories[conversation_id]`. A single global history would mix different users'
conversations together. Verified by sending the same follow-up question under two ids: one
answered in context, the other asked for clarification.

**6. Tool descriptions are the routing logic.**
Claude picks a tool based only on its description, so the wording decides the routing.
`search_issues` is described for bugs; `search_web` for current docs, newer fixes, and
following up on pull-request links. In production logs, a how-to question went straight to
`search_web` and a bug report went to `search_issues`.

**7. One repo, one command locally; each service on the platform that suits it.**
Backend and frontend share a repo so a change that touches both lands in one commit, and
`docker compose up` runs the whole stack without installing Python or Node. Production doesn't
use Compose: Render builds `backend/` and Vercel builds `frontend/`, each pointed at its folder,
and a change outside a service's folder doesn't redeploy it. The frontend's git history was
brought in with `git subtree`, so no commits were lost in the merge.

## Known limitations

- **History grows without limit.** Every call resends the conversation's full history,
  including tool results, so token cost rises with each turn and a long conversation will
  eventually hit the context limit. Fix: trim or summarise older turns.
- **Memory lives in the server process.** It is lost on restart and whenever the free instance
  sleeps, and it would not be shared across multiple instances.
- **Static data.** The issue set is a snapshot with no automatic refresh. Planned: a scheduled
  job that embeds only new issues.
- **Truncation instead of chunking** — ~4% of issues lose their trailing discussion.
- **Neighbouring results can bleed in.** Each search returns 3 issues, and Claude sometimes
  blends advice from a related issue into the answer.
- **`/ask` has no authentication or rate limiting** — planned.
- **No streaming** — answers arrive all at once. Planned.

## Backend only (without Docker)

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env` as in Quick start, then start the API and open
http://127.0.0.1:8000/docs:

```bash
uvicorn main:app --reload
```

Example request:

```bash
curl -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "CircularProgress renders as a white square in dark mode", "conversation_id": "demo-1"}'
```

Backend container on its own (from the repo root):

```bash
docker build -t mui-backend backend/
docker run --rm -p 8000:8000 --env-file backend/.env mui-backend
```

### Rebuilding the issue index (optional)

`backend/chroma_db/` is committed, so this is only needed to refresh the data. Add
`GITHUB_TOKEN` to `backend/.env`, then from `backend/`:

```bash
python ingest.py   # fetches issues + comments from GitHub → issues.json
rm -rf chroma_db
python embed.py    # embeds every issue → chroma_db/  (201 paid embedding calls)
```

## Deployment

- **Backend → Render**, as a Docker web service with *Root Directory* `backend`, auto-deploying
  on pushes to `main` that touch `backend/`. Three secrets are set as environment variables in
  Render (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `TAVILY_API_KEY`); none are in the image.
  `GET /` is a health check that Render polls before routing traffic to a new deploy.
- **Frontend → Vercel**, with *Root Directory* `frontend`. Its only environment variable is
  `BACKEND_URL`. Details in [frontend/README.md](frontend/README.md).

On both platforms a failed build doesn't replace the live deploy — the previous version keeps
serving.

## Files (backend)

| File | Purpose |
|---|---|
| `backend/main.py` | FastAPI app: `GET /` health check, `POST /ask` |
| `backend/agent.py` | Tools, tool schemas, and the Claude tool-use loop with per-conversation memory |
| `backend/embed_util.py` | Shared embedding function (build time and query time) |
| `backend/ingest.py` | Fetches issues and comments from the GitHub API |
| `backend/embed.py` | One-off build script: filters, embeds, and stores issues in Chroma |
| `backend/chroma_db/` | The committed vector index |
| `backend/Dockerfile` | Python 3.11-slim image; dependencies installed before code for layer caching |
| `docker-compose.yml` | Runs backend + frontend together on one network |

**Stack:** Python · FastAPI · Anthropic Claude (tool use) · OpenAI embeddings · Chroma · Tavily ·
Next.js · Docker / Docker Compose · Render · Vercel