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

response = claude_client.messages.create(
    model="claude-sonnet-4-5",
    max_tokens=1045,
    tools=tools,
    messages=[{"role": "user", "content": user_question}],
)

print(response.content)
