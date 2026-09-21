from openai import OpenAI
from dotenv import load_dotenv
import json

load_dotenv()
client = OpenAI()


issue_data = []

with open("issues.json", "r") as f:
    issue_data = json.load(f)

filter_issue = [issue for issue in issue_data if issue["response_comment"]]

documents = []
ids = []

for issue in filter_issue:
    comments = "\n".join(issue["response_comment"])
    blob = issue["title"] + "\n" + issue["body"] + "\n" + comments
    ids.append(str(issue["number"]))
    documents.append(blob)
