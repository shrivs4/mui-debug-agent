import json
import random
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()
client = Anthropic()

issues = []

with open("issues.json", "r") as f:
    issues = json.load(f)

filter_issues = [issue for issue in issues if issue["response_comment"]]

random.seed(42)

sample_issues = random.sample(filter_issues, 30)

PROMPT = """Here is a GitHub issue from the MUI repository.

Title: {title}
Body: {body}

Write the question a developer would type into a help chat when they hit this bug.
Rules:
- Describe the symptom in plain words, as if you don't know the cause.
- Do NOT reuse distinctive words or phrases from the title.
- One or two sentences. Output only the question."""

test_set = []

for issue in sample_issues:
    body = (issue["body"] or "")[:1500]
    response = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=150,
        messages=[
            {"role": "user", "content": PROMPT.format(title=issue["title"], body=body)}
        ],
    )
    question = response.content[0].text.strip()
    test_set.append({"question": question, "expected_id": str(issue["number"])})


with open("eval/retrieval_set.json", "w") as f:
    json.dump(test_set, f, indent=2)
