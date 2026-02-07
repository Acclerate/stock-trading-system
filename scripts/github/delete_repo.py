import requests
import json
import os
import sys

# Get token from environment variable
token = os.getenv('GITHUB_TOKEN')
if not token:
    print("Error: GITHUB_TOKEN environment variable not set")
    print("Usage: GITHUB_TOKEN=your_token python delete_repo.py")
    sys.exit(1)

# Old repository info
owner = "Acclerate"
repo = "stockScience"

# API endpoint
url = f"https://api.github.com/repos/{owner}/{repo}"

# Request headers
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

print(f"Delete repository: {owner}/{repo}")
print("WARNING: This operation cannot be undone!")

# Delete request
response = requests.delete(url, headers=headers)

if response.status_code == 204:
    print("Repository deleted successfully!")
    print(f"Deleted: https://github.com/{owner}/{repo}")
elif response.status_code == 404:
    print("Repository not found or already deleted")
else:
    print(f"Delete failed: {response.status_code}")
    print(response.text)
