import json
import chromadb
from embed_util import embed_text

collection = chromadb.PersistentClient(path="./chroma_db").get_collection("MUIIssueDoc")


def dense_search(query, k):
    result = collection.query(query_embeddings=[embed_text(query)], n_results=k)
    return result["ids"][0]  # list of issue ids, best match first


issues = []

with open("eval/retrieval_set.json", "r") as f:
    issues = json.load(f)

hit_score = 0


for issue in issues:
    result = dense_search(issue["question"], 3)
    if issue["expected_id"] in result:
        hit_score += 1
    else:
        print("MISS:", issue["expected_id"], "|", issue["question"])
        print("   got:", result)

print((hit_score / len(issues)) * 100)
