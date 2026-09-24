import chromadb
from embed_util import embed_text
from anthropic import Anthropic
from dotenv import load_dotenv
import json

load_dotenv()

chroma_client = chromadb.PersistentClient(path="./chroma_db")

collection = chroma_client.get_collection(name="MUIIssueDoc")

claude_client = Anthropic()


def search_issues(query):
    embeded_query = embed_text(query)
    result = collection.query(query_embeddings=[embeded_query], n_results=3)
    return result


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
    }
]

required_tools = {"search_issues": search_issues}

user_question = "My MUI CircularProgress renders as a white square in dark mode"


def call_claude(query):
    response = claude_client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=1024,
        tools=tools,
        messages=[{"role": "user", "content": query}],
    )
    final_response = response
    messages_list = [{"role": "user", "content": query}]
    tool_use_status = response.stop_reason
    attempt = 0
    while tool_use_status == "tool_use" and attempt < 10:
        tool_response = []
        for block in final_response.content:
            if block.type == "tool_use":
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

    return final_response.content[0]


call_claude(user_question)
print(call_claude(user_question))
