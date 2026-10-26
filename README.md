# MUI Debug Agent

An AI agent that debugs Material UI (MUI) problems. Describe a bug or paste an error, and it
searches how similar issues were actually resolved, reads the official MUI docs for your
version, and streams back a concrete fix.

**Live demo:** [mui-debug-fe.vercel.app](https://mui-debug-fe.vercel.app/)

> The backend runs on Render's free tier and sleeps when idle, so the first request after a
> quiet period can take up to a minute.

Version 1 of this project proved I could build an agent. Version 2 is about **running one**:
auth, rate limiting, a scope guard, streaming, tracing and cost tracking, evals, and a data
pipeline that refreshes itself. Every change below was measured, and two planned changes
were dropped because the measurements said they weren't worth it.

## Results at a glance

| What | Result |
|---|---|
| Retrieval (does the right past issue come back in the top 3?) | **25 / 26** paraphrased user questions |
| Scope guard (does it block off-topic and let MUI questions through?) | **19 / 20**, including prompt-injection and follow-up cases |
| Tool-loop fix (one system-prompt change, measured in Langfuse) | **4–5 → 2** tool calls · **$0.25–0.37 → $0.11** per question · **38–51 s → 25 s** |
| Time to first visible content (streaming) | **~17 s → ~1 s** (total time unchanged) |
| Off-topic request cost | one Haiku call, **< $0.001** |
| Rate-limited request cost | **0 ms, no API call** |
| Backend memory on Render (incl. Node for MCP, tracing) | **~173 MB of 512 MB** |

## Repository layout

A monorepo: the agent backend and the chat UI live side by side and run together with one
command.

```
.
├── backend/                  FastAPI service + Claude agent (deployed on Render)
│   └── eval/                 Retrieval and scope evals (see "Evals")
├── frontend/                 Next.js chat UI (deployed on Vercel) — see frontend/README.md
├── .github/workflows/        Weekly re-embed pipeline (GitHub Actions)
└── docker-compose.yml        Runs the whole stack locally
```

## What it does

Claude (Sonnet) runs a tool-use loop and decides which tools to call for each question:

- **`search_issues`** — semantic search over ~200 closed MUI GitHub issues that have a human
  answer (OpenAI embeddings + Chroma). Each match carries the problem *and* how it was fixed.
- **`useMuiDocs` / `fetchDocs`** — the official **MUI MCP server**: finds the right docs page
  for the user's MUI version and fetches it. `fetchDocs` URLs are checked against an allowlist.
- **`search_web`** — Tavily web search, **restricted to trusted sources** (mui.com, GitHub,
  Stack Overflow, MDN, react.dev).

Typical routes: a how-to question goes `useMuiDocs → fetchDocs`; a bug report starts with
`search_issues`. Conversations have memory per `conversation_id`, and answers **stream** to
the browser as they are written, with a status line while tools run ("Reading the MUI docs…").

## Architecture

```
Browser
 → Next.js route /api/ask (Vercel, server-side)
     adds X-API-Key + real client IP, forwards the abort signal, passes the stream through
 → FastAPI POST /ask (Render)
     1. API key check            → 401        (constant-time compare, fails closed)
     2. Rate limit (per IP)      → 429        (sliding window, 10 / 60 s)
     3. Scope guard (Haiku)      → refusal    (fails closed)
     4. Agent loop (Sonnet, streamed)
          ⇄ search_issues   (OpenAI embeddings + Chroma, top 3)
          ⇄ MUI MCP server  (useMuiDocs, fetchDocs — Node subprocess over stdio)
          ⇄ search_web      (Tavily, trusted domains only)
 ← NDJSON stream: status / text / done / error events

Side channels:
 - every request → one structured JSON log line (status, tools, latency; no raw IP)
 - every request → one Langfuse trace (guard → each Claude turn → each tool, with tokens + cost)
 - every Monday  → GitHub Action re-fetches + re-embeds the issues, commits, Render redeploys
```

The order of steps 1–3 is deliberate: only trusted callers count against the rate limit, and
blocked requests cost nothing. The logs prove it — a rate-limited request takes 0 ms and makes
no API call; a refused one costs a single ~600 ms Haiku call.

## Key design decisions

### Retrieval and data

**1. Embed the problem, carry the fix.** Each issue is one document: title + body + human
comments. When an issue matches, Claude gets the problem and its resolution in one retrieval.
(Issues without a human comment are dropped — a bug with no answer is dead weight.)

**2. OpenAI embeddings; Chroma only stores and searches.** Chroma's default embeds with a local
model, which adds a heavy ML runtime to the container. Embedding through the API
(`text-embedding-3-small`) keeps memory low. The same function (`embed_util.py`) is used at
build time and query time — mixing models would break retrieval.

**3. Truncate long issues at 8,000 characters.** ~4% of issues exceeded the embedding model's
limit. Truncation keeps the title and the start of the body — the part that describes the
problem. Proper chunking is the real fix.

**4. The index is committed, and a weekly Action keeps it fresh.** A GitHub Action
(`.github/workflows/re-embed.yml`) runs every Monday and on demand: fetch issues → embed →
**commit `chroma_db/` back to `main` only if the data changed** → Render redeploys. The runner
is thrown away after each run, so committing back is how the new data reaches production
without adding a hosted database.
- It **rebuilds the collection from scratch**. Chroma's `add` silently skips ids that already
  exist (no error, no warning — I tested it), so an incremental re-run would never update an
  issue or remove one that dropped out.
- It **fails safe**: if any step fails, the commit step never runs and production keeps last
  week's data.
- It installs only the 4 packages the scripts need, pinned to the same versions as production,
  so the Chroma file format the Action writes is the one Render reads.

### Security and cost protection

**5. A shared secret between two servers, not user auth.** The browser never calls the
backend — the Next.js route does, server-side. So the gap was anyone calling the Render URL
directly. Fix: a shared API key in a header, compared with `secrets.compare_digest`. My first
version **failed open**: with the key unset, `None == None` let everyone in. It now rejects
everything if the server key is missing. A JWT would be the tool for many users with
identities; there is one trusted caller.

**6. Rate limiting behind two proxies.** FastAPI's `request.client.host` is Render's load
balancer, so a naive per-IP limit would throttle all users together. The Next.js route forwards
the real IP as `X-Client-IP`, and the backend trusts that header **only because** the request
already passed the shared key. Sliding window: per IP, the timestamps of the last 60 seconds.

**7. A cheap scope guard in front of the expensive loop.** A Haiku classifier decides whether
the question is about MUI before any Sonnet call. It sees the previous question, so short
follow-ups ("and in v5?") pass, and it fails closed. An off-topic request costs one tiny call
instead of a multi-tool loop.

**8. `fetchDocs` URL allowlist (indirect prompt injection).** The MCP server fetches whatever
URL the model passes. URLs are checked by **hostname suffix** (`.mui.com`), not substring —
`evil.com/?q=mui.com` and `mui.com.evil.com` both pass a substring check. My first exact-match
version would have blocked MUI's own `llms.mui.com`, which an end-to-end test caught. Web
search is restricted to trusted domains for the same reason.

### Streaming

**9. NDJSON over one POST, with two kinds of events.** Only the final answer is text the model
streams; tool steps aren't. So one stream carries `status` events while tools run and `text`
deltas while Claude writes, then `done` (or `error`). I chose NDJSON over SSE because
`EventSource` is GET-only and `/ask` is a POST.

**10. Checks before the stream, errors inside it.** Once a stream starts, the `200` is already
sent — my own logs showed `200 OK` before any tool ran. So auth, rate limit and the guard run
first and keep real status codes; anything that fails mid-stream becomes an `error` event.

**11. Cancellation end to end.** The Next.js route forwards the browser's abort signal; when
the browser goes away, the backend's generator is cancelled and the Claude stream closes, so
nobody pays for an answer no one is reading.

**12. Streaming doesn't make the agent faster.** Total time stayed the same; time to first
content dropped from ~17 s to ~1 s. The frontend also reveals text at an adaptive pace so fast
bursts don't look jumpy.

### Running it

**13. MUI's MCP server inside the Python image.** `@mui/mcp` needs Node ≥ 22. A multi-stage
Dockerfile installs the pinned package in a Node image and copies only the `node` binary and
the package into the Python image — no npm, no runtime downloads. An env var lets the same code
run `npx` locally and the baked-in binary in the container. The server starts in FastAPI's
lifespan, with a readiness check before traffic is served.

**14. Tracing that survives streaming.** Two layers, both OpenTelemetry: Langfuse's `@observe()`
creates one trace per `/ask`, and the Anthropic instrumentor adds a child span per Claude call
with tokens and cost. With streaming, the handler returns *before* the work happens, so a
simple tracing wrapper would end the trace too early; Langfuse special-cases
`StreamingResponse` and ends it when the stream finishes. Spans are batched, so the lifespan
flushes them on shutdown — otherwise every redeploy would drop the last traces.

**15. One structured log line per request.** `status`, `tools`, `answer_chars`, `latency_ms`,
`conversation_id`, first 100 characters of the question. The raw IP is deliberately not logged
(it is personal data under GDPR). The first live day of logging found a guard false negative
and a six-tool loop — both became eval cases.

### Measure before building

**16. Hybrid search was planned and dropped.** Dense search scored 25/26 on the retrieval eval.
The one miss was a vocabulary gap — the user said "flatter", the issue said "elevation" —
which keyword search (BM25) can't fix either, since the words don't overlap. Adding BM25 + RRF
would have added complexity for at most one question.

**17. The guard stays strict, with one known false negative.** The scope eval caught the
production case ("Is there a mail template in MUI?" is refused — the model reads it as an email
question). A targeted prompt rule had no measurable effect and was reverted. A "when in doubt,
allow" rule was rejected: any text mentioning MUI would pass, weakening the gate against
off-topic and injection requests. A refused user can rephrase; a wider gate stays open for
everyone.

**18. The tool-loop fix, measured.** Langfuse traces showed the agent repeating tools (docs →
web → docs again), and every round re-sends a growing context — one question cost up to
$0.37. Three system-prompt rules (use as few calls as needed, with default routes; don't repeat
a similar call unless the result was missing something; answer as soon as you can) took it to
2 calls, $0.11 and 25 s across repeated runs. The same traces showed answers being cut off at
`max_tokens=1024`, which is now 2048.

**19. No `temperature` on the guard.** Newer Claude models reject non-default sampling
parameters with HTTP 400. Because the guard fails closed, setting one would make a future model
upgrade silently refuse every question. Stability is measured instead, by re-running the eval.

## Evals

Run from `backend/` (they need the same `.env` as the app):

```bash
python -m eval.eval_retrieval   # Hit@3 over eval/retrieval_set.json
python -m eval.eval_scope       # guard accuracy, per group, over eval/scope_set.json
```

- **Retrieval eval (known-item).** 30 random issues; Haiku rewrote each as the question a
  developer would type, without reusing the title's words (using the exact title would leak —
  the title is inside the embedded text). I reviewed the labels and removed 4 internal/meta
  threads, leaving 26. Scored at top 3 because that is what production gives Claude.
- **Scope eval.** 20 hand-labelled questions in four groups — clearly in scope, clearly out,
  tricky in ("does MUI have X?", build errors while using MUI, follow-ups), tricky out (other UI
  libraries, prompt injection, topic switches). Roughly balanced, so an always-yes guard would
  score 55%.
- `eval/build_retrieval_set.py` created the retrieval set. **Don't re-run it** — it would
  re-sample from the current data and overwrite the hand-cleaned set.

## Known limitations

**Agent and memory**
- **Conversation memory lives in the server process.** Lost on restart, redeploy (now at least
  weekly) and when the free instance sleeps; not shared across instances.
- **History grows without limit.** Each turn re-sends the whole conversation, including tool
  results, so cost rises per turn. Fix: trim or summarise older turns.
- **Search tools are synchronous** inside the async request path, so they briefly block the
  event loop. Fine at this scale; `asyncio.to_thread` would fix it. A cancelled stream also
  can't interrupt a sync tool mid-run.
- **Runs on the Claude 4.5 generation** (Haiku 4.5 guard, Sonnet 4.5 agent). Upgrading is a
  deliberate change: re-run both evals after.

**Data and retrieval**
- **~13% of the corpus is internal/meta threads** (CI tracking, release chores, audits) that can
  never help a user — found while building the eval. Fix: add `label:bug` to the ingest query.
- `ingest.py` takes the GitHub Search API's default ("best match") order, not the newest issues.
- Truncation instead of chunking (~4% of issues lose trailing discussion).
- Each search returns 3 issues, and advice from a neighbouring issue can bleed into an answer.
- **The retrieval eval is tied to the current data.** After a weekly re-embed, an expected issue
  can drop out of the top 300 and count as a miss even though search is fine.
- The retrieval set may be somewhat easy: Haiku read the issue body, which is also embedded.
  A harder set — questions about bugs *not* in the database — would test a different failure.

**Pipeline**
- **Scheduled runs are best-effort.** The first scheduled Monday run did not fire; GitHub can
  delay or drop scheduled workflows under load, especially at the top of the hour. The cron now
  runs at minute 17. For anything that must run on time: a real scheduler, or an alert when the
  run is missing.
- Committing the index back stores a full ~3 MB copy in git history each week the data
  changes (~160 MB/year). Fine here; at scale, a hosted vector database.
- Every run re-embeds all ~200 issues (a few cents). A content hash would make it incremental.
- Running the backend locally modifies `chroma_db/` (Chroma writes bookkeeping even on reads) —
  check `git status` before committing.

**Security**
- **Rate limiter state is in process memory** — resets on restart, isn't shared across
  instances (would need Redis), and keeps an entry for every IP it has seen.
- The rate limit trusts `X-Client-IP` only because of the API key; if the key leaked, fake IPs
  could bypass it. One shared key, no rotation process yet (rotate = update Render and Vercel
  together).
- The web filter's `github.com` entry covers all of GitHub; old `v4.mui.com` docs can appear.
- The `fetchDocs` allowlist trusts any `*--material-ui-docs.netlify.app` host (MUI's preview
  deploy naming).
- **Guard false negative** on component-availability questions phrased like email content (see
  decision 17).

**Streaming and observability**
- A stream that fails after some text keeps the partial answer; Retry appends a new answer below.
- Cancelled requests write no log line.
- Traces aren't grouped into Langfuse sessions per conversation yet (needs testing with
  streaming). MCP tool spans don't record their inputs (the first argument is the whole MCP
  session object, ~270 KB per span).
- MCP tool descriptions are sent with every Claude call and cost tokens.

## Running locally

### Whole stack (Docker)

Create `backend/.env` (no quotes around values):

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
TAVILY_API_KEY=...
BACKEND_API_KEY=...          # any long random string, e.g.
                             # python -c "import secrets; print(secrets.token_urlsafe(32))"
LANGFUSE_PUBLIC_KEY=...      # optional: tracing
LANGFUSE_SECRET_KEY=...
LANGFUSE_BASE_URL=https://cloud.langfuse.com
```

and `frontend/.env.local` with the **same** `BACKEND_API_KEY`. Then, from the repo root:

```bash
docker compose up --build
```

Open http://localhost:3000. Compose builds both images, puts them on a shared network and
points the frontend at the backend by service name (`http://backend:8000`).

### Backend only

```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
set -a; source .env; set +a
uvicorn main:app --reload
```

Locally the MUI MCP server is started with `npx` (needs Node ≥ 22). Example request:

```bash
curl -N -X POST http://127.0.0.1:8000/ask \
  -H "Content-Type: application/json" \
  -H "X-API-Key: $BACKEND_API_KEY" \
  -d '{"question": "CircularProgress renders as a white square in dark mode", "conversation_id": "demo-1"}'
```

`-N` turns off curl's buffering so you can watch the NDJSON events arrive.

### Rebuilding the issue index by hand

Normally the weekly Action does this (Actions tab → **Weekly re-embed** → **Run workflow**).
By hand, add `GITHUB_TOKEN` to `backend/.env`, then from `backend/`:

```bash
python ingest.py   # GitHub issues + comments → issues.json
python embed.py    # rebuilds the Chroma collection from scratch
```

## Deployment

- **Backend → Render**, Docker web service, *Root Directory* `backend`, auto-deploys on commits
  to `main`. Secrets as environment variables: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`,
  `TAVILY_API_KEY`, `BACKEND_API_KEY`, and the three `LANGFUSE_*` keys. `GET /` is the health
  check Render polls before switching traffic to a new deploy.
- **Frontend → Vercel**, *Root Directory* `frontend`, environment variables `BACKEND_URL` and
  `BACKEND_API_KEY`.
- **Weekly re-embed → GitHub Actions**, repo secret `OPENAI_API_KEY`; GitHub provides a fresh
  `GITHUB_TOKEN` for each run.
- **Deploy order for new secrets:** set them on the host(s) first, then merge — otherwise the
  new code goes live expecting a value that isn't there yet.

On both platforms a failed build doesn't replace the live deploy.

## Files (backend)

| File | Purpose |
|---|---|
| `main.py` | FastAPI app: lifespan (MCP startup + readiness, trace flush), `GET /`, `POST /ask` (auth → rate limit → guard → NDJSON stream), structured logging |
| `agent.py` | Tools, scope guard, streamed Claude tool-use loop, MCP tool calls + URL allowlist, tracing decorators |
| `constant.py` | Agent system prompt, allowed web domains and doc hosts, MCP server config, tool status labels |
| `embed_util.py` | Shared embedding function (build time and query time) |
| `ingest.py` | Fetches closed issues + human comments from the GitHub API → `issues.json` |
| `embed.py` | Rebuilds the Chroma collection from `issues.json` |
| `chroma_db/` | The committed vector index (refreshed weekly by the Action) |
| `eval/` | Retrieval and scope evals with their test sets |
| `requirements-embed.txt` | The 4 packages the weekly Action installs |
| `Dockerfile` | Multi-stage: Node stage for `@mui/mcp`, Python 3.11-slim runtime |

**Stack:** Python · FastAPI · Anthropic Claude (Haiku guard, Sonnet agent, tool use, streaming) ·
MCP · OpenAI embeddings · Chroma · Tavily · Langfuse / OpenTelemetry · Next.js · Docker /
Docker Compose · GitHub Actions · Render · Vercel
