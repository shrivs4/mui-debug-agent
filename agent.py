import chromadb
from embed_util import embed_text
from anthropic import Anthropic
from dotenv import load_dotenv
import json
from tavily import TavilyClient

load_dotenv()

chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_collection(name="MUIIssueDoc")

claude_client = Anthropic()

tavily_client = TavilyClient()


def search_issues(query):
    embeded_query = embed_text(query)
    result = collection.query(query_embeddings=[embeded_query], n_results=3)
    return result


def search_web(query):
    web_result = tavily_client.search(query)
    return web_result


tools = [
    {
        "name": "search_issues",
        "description": "Search a database of past MUI (Material UI) GitHub issues for bugs similar to the user's error, returning matching issues and their resolutions",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's error message or a description of the MUI bug to search for",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the live web for current MUI documentation, "
        "recent fixes, or information not found in the local issues database. "
        "Use when the issue search returns nothing relevant, or when the resolution found is only a link to a pull request and "
        "needs more detail.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The user's error message or a description of the MUI bug to search for",
                }
            },
            "required": ["query"],
        },
    },
]

required_tools = {"search_issues": search_issues, "search_web": search_web}

messages_list = []


def call_claude(query):
    messages_list.append({"role": "user", "content": query})
    response = claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        tools=tools,
        messages=messages_list,
    )
    final_response = response
    tool_use_status = response.stop_reason
    attempt = 0
    while tool_use_status == "tool_use" and attempt < 10:
        tool_response = []
        for block in final_response.content:
            if block.type == "tool_use":
                print("TOOL CALLED:", block.name, "|", block.input)
                tools_to_call = required_tools[block.name]
                response_data = tools_to_call(**block.input)
                tool_response.append(
                    {"id": block.id, "result": json.dumps(response_data)}
                )
        messages_list.append({"role": "assistant", "content": final_response.content})

        content = []

        for result in tool_response:
            content.append(
                {
                    "type": "tool_result",
                    "tool_use_id": result["id"],
                    "content": result["result"],
                }
            )

        messages_list.append({"role": "user", "content": content})

        final_response = claude_client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            tools=tools,
            messages=messages_list,
        )

        tool_use_status = final_response.stop_reason
        attempt += 1
    messages_list.append({"role": "assistant", "content": final_response.content})
    return final_response.content[0].text


user_question = "What is the latest stable version of MUI Material and what were the breaking changes in it?"
print(call_claude(user_question))
print(call_claude("what file should I change?"))
