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
