from fastapi.responses import StreamingResponse
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from agent import call_claude, get_previous_question, is_mui, to_claude_tools
from contextlib import asynccontextmanager
import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from constant import MUI_MCP_SERVER
import os
import secrets
import time
import json
import logging
from langfuse import observe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mui-agent")


def log_request(**fields):
    logger.info(json.dumps(fields))


@asynccontextmanager
async def lifespan(app):
    async with stdio_client(MUI_MCP_SERVER) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            for attempt in range(15):
                result = await session.list_tools()
                names = [tool.name for tool in result.tools]
                if "useMuiDocs" in names:
                    print(f"MCP ready after {attempt + 1} attempt(s): {names}")
                    break
                await asyncio.sleep(1)
            else:
                print("WARNING: useMuiDocs unavailable; continuing with fetchDocs only")
            app.state.mcp_session = session
            app.state.mcp_tools = to_claude_tools(result.tools)
            print("Tools from Claude:", [t["name"] for t in app.state.mcp_tools])
            yield
    print("MCP connection closed")


app = FastAPI(lifespan=lifespan)

permission_key = os.getenv("BACKEND_API_KEY")


class Question(BaseModel):
    question: str
    conversation_id: str


request_times = {}
LIMIT = 10
WINDOW_SECONDS = 60


def is_rate_limited(ip: str):
    now = time.time()

    recent = [t for t in request_times.get(ip, []) if now - t < WINDOW_SECONDS]

    if len(recent) >= LIMIT:
        request_times[ip] = recent
        return True

    recent.append(now)
    request_times[ip] = recent
    return False


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/ask")
@observe()
async def ask(body: Question, request: Request):
    start = time.perf_counter()

    def ms():
        return round((time.perf_counter() - start) * 1000)

    sent_key = request.headers.get("X-API-Key")
    client_ip = request.headers.get("X-Client-IP", "unknown")

    if not permission_key or not secrets.compare_digest(sent_key or "", permission_key):
        log_request(status="unauthorized", latency_ms=ms())
        raise HTTPException(status_code=401, detail="Unauthorized")

    if is_rate_limited(client_ip):
        log_request(
            status="rate_limited", conversation_id=body.conversation_id, latency_ms=ms()
        )
        raise HTTPException(status_code=429, detail="Too Many Requests")

    previous = get_previous_question(body.conversation_id)
    question = body.question

    def line(event):  # one NDJSON line
        return json.dumps(event) + "\n"

    if not await is_mui(question, previous):
        log_request(
            status="refused",
            conversation_id=body.conversation_id,
            question=question[:100],
            latency_ms=ms(),
        )

        async def refusal():
            yield line(
                {
                    "type": "text",
                    "delta": "I can only help with MUI (Material UI, MUI X, Joy UI) questions — bugs, errors, theming or styling. Try asking about a component that isn't behaving.",
                }
            )
            yield line({"type": "done"})

        return StreamingResponse(refusal(), media_type="application/x-ndjson")

    async def event_stream():
        tools_used = []
        answer_chars = 0
        try:
            async for event in call_claude(
                question,
                body.conversation_id,
                request.app.state.mcp_session,
                request.app.state.mcp_tools,
                tools_used,
            ):
                if event["type"] == "text":
                    answer_chars += len(event["delta"])
                yield line(event)
            yield line({"type": "done"})
            log_request(
                status="ok",
                conversation_id=body.conversation_id,
                question=question[:100],
                tools=tools_used,
                answer_chars=answer_chars,
                latency_ms=ms(),
            )
        except Exception as e:
            log_request(
                status="error",
                conversation_id=body.conversation_id,
                error=str(e)[:200],
                latency_ms=ms(),
            )
            yield line(
                {"type": "error", "message": "Something went wrong. Please try again."}
            )

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")
