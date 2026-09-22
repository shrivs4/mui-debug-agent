import json
from unittest import result
from embed_util import embed_text
import chromadb

chroma_client = chromadb.Client()

collection = chroma_client.get_or_create_collection(name="MUIIssueDoc")

issue_data = []

with open("issues.json", "r") as f:
    issue_data = json.load(f)

filter_issue = [issue for issue in issue_data if issue["response_comment"]]

documents = []
ids = []
embeddings = []

for issue in filter_issue:
    comments = "\n".join(issue["response_comment"])
    blob = issue["title"] + "\n" + issue["body"] + "\n" + comments
    blob = blob[:8000]
    ids.append(str(issue["number"]))
    documents.append(blob)
    embeddings.append(embed_text(blob))

collection.add(documents=documents, ids=ids, embeddings=embeddings)

query = """bug: Circular Progress briefly renders as white square on repeated page reloads (Material UI, Dark Mode)
### Steps to reproduce
Steps:
1. Go to react progress component examples
2. Use dark mode
3. Press F5 multiple times to reload the page.
4. Observe the circular progress components; it may briefly render as a white square before becoming circular.
### Current behavior
When rapidly refreshing the page in dark mode, the Material UI circular progress indicator sometimes initially appears as a white square before rendering correctly as a circle."""

query_vector = embed_text(query)

result = collection.query(query_embeddings=query_vector, n_results=3)

print(result)
