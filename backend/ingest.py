from dotenv import load_dotenv
import os
import requests
import json

load_dotenv()
token = os.getenv("GITHUB_TOKEN")

header = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}

url = "https://api.github.com/search/issues?q=repo:mui/material-ui+is:issue+is:closed&per_page=100"

issue_data = []


def getIssue(page):
    enhancedUrl = f"{url}&page={page}"
    response = requests.get(enhancedUrl, headers=header)
    data = response.json()
    return data["items"]


for page in range(1, 4):
    issue_data += getIssue(page)


def extract_resolution(number):
    response = requests.get(
        f"https://api.github.com/repos/mui/material-ui/issues/{number}/comments",
        headers=header,
    )
    response_data = response.json()
    user_response = [c["body"] for c in response_data if c["user"]["type"] != "Bot"]
    return user_response


enhanced_list = []

for issue in issue_data:
    response_comment = extract_resolution(issue["number"])
    new_object = {
        "number": issue["number"],
        "title": issue["title"],
        "body": issue["body"],
        "response_comment": response_comment,
    }
    enhanced_list.append(new_object)

with open("issues.json", "w") as f:
    json.dump(enhanced_list, f, indent=2)
