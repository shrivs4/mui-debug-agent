from mcp import StdioServerParameters
import os

ALLOWED_WEB_DOMAINS = [
    "mui.com",
    "github.com",
    "stackoverflow.com",
    "developer.mozilla.org",
    "react.dev",
]

AGENT_SYSTEM_PROMPT = """
You help developers debug MUI problems (Material UI, MUI X, Joy UI).
- For anything unrelated, politely decline and say what you can help with.
- Give concrete fixes. If the tools found nothing relevant, say so honestly rather than guessing.
"""

entry = os.getenv("MUI_MCP_ENTRY")
if os.getenv("MUI_MCP_ENTRY"):
    MUI_MCP_SERVER = StdioServerParameters(command="node", args=[entry])
else:
    MUI_MCP_SERVER = StdioServerParameters(command="npx", args=["-y", "@mui/mcp@0.1.7"])


ALLOWED_MCP_TOOLS = ["useMuiDocs", "fetchDocs"]

ALLOWED_DOC_HOSTS = ["mui.com", "--material-ui-docs.netlify.app"]
ALLOWED_DOC_SUFFIXES = [".mui.com", "--material-ui-docs.netlify.app"]
