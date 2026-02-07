import requests
import json
import os
import sys

# Get token from environment variable
token = os.getenv('GITHUB_TOKEN')
if not token:
    print("Error: GITHUB_TOKEN environment variable not set")
    print("Usage: GITHUB_TOKEN=your_token python create_repo.py")
    sys.exit(1)

# API endpoint
url = "https://api.github.com/user/repos"

# Request headers
headers = {
    "Authorization": f"token {token}",
    "Accept": "application/vnd.github.v3+json"
}

# Repository configuration
data = {
    "name": "stock-trading-system",
    "description": "Personal quantitative trading analysis system - using Diggold SDK for stock data analysis and trading strategy research",
    "private": False,
    "auto_init": False
}

# Create request
response = requests.post(url, headers=headers, data=json.dumps(data))

if response.status_code == 201:
    repo_info = response.json()
    print("Repository created successfully!")
    print(f"Name: {repo_info['name']}")
    print(f"URL: {repo_info['html_url']}")
    print(f"Clone URL: {repo_info['clone_url']}")
elif response.status_code == 422:
    print("Error: Repository already exists or invalid name")
    print(response.text)
else:
    print(f"Error: {response.status_code}")
    print(response.text)
