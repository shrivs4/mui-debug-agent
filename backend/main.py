from fastapi import FastAPI, Request
from pydantic import BaseModel
from agent import call_claude, get_previous_question, is_mui, to_claude_tools
from contextlib import asynccontextmanager
import asyncio
from mcp import ClientSession
from mcp.client.stdio import stdio_client
from constant import MUI_MCP_SERVER


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


class Question(BaseModel):
    question: str
    conversation_id: str


@app.get("/")
def health_check():
    return {"status": "ok"}


@app.post("/ask")
async def ask(body: Question, request: Request):
    previous = get_previous_question(body.conversation_id)
    question = body.question
    if not await is_mui(question, previous):
        return {
            "answer": """I can only help with MUI (Material UI, MUI X, Joy UI) questions — bugs, errors, theming or styling. Try asking about a component that isn't behaving."""
        }
    else:
        conversation_id = body.conversation_id
        response = await call_claude(
            question,
            conversation_id,
            request.app.state.mcp_session,
            request.app.state.mcp_tools,
        )
        return {"answer": response}
