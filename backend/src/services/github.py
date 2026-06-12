import requests
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

def get_github_auth_url() -> str:
    return f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo"

def exchange_code_for_token(code: str) -> str:
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        json={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code
        }
    )
    return response.json().get("access_token")

def get_user_repos(access_token: str) -> list:
    response = requests.get(
        "https://api.github.com/user/repos",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    return response.json()

def get_user_info(access_token: str) -> dict:
    response = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        }
    )
    return response.json()

def create_webhook(access_token: str, repo_full_name: str, webhook_url: str) -> dict:
    response = requests.post(
        f"https://api.github.com/repos/{repo_full_name}/hooks",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        json={
            "name": "web",
            "active": True,
            "events": ["push"],
            "config": {
                "url": webhook_url,
                "content_type": "json"
            }
        }
    )
    return response.json()

def get_file_content(access_token: str, repo_full_name: str, file_path: str, ref: str = "main") -> str:
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3.raw"
        },
        params={"ref": ref}
    )
    if response.status_code == 200:
        return response.text
    return ""

def delete_webhook(access_token, repo_full_name, webhook_id):
    url = f"https://api.github.com/repos/{repo_full_name}/hooks/{webhook_id}"
    headers = {
        "Authorization": f"token {access_token}",
        "Accept": "application/vnd.github.v3+json"
    }
    response = requests.delete(url, headers=headers)
    return response.status_code == 204

def fetch_repo_branches(access_token: str, repo_full_name: str) -> list:
    """Fetch all branches of a repository (name + head commit sha)."""
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/branches",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        params={"per_page": 100}
    )
    if response.status_code != 200:
        return []
    return response.json()


def fetch_commits_for_ref(access_token: str, repo_full_name: str, ref: str, per_page: int = 50) -> list:
    """Fetch the most recent commits reachable from a given ref (branch head)."""
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/commits",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        params={"sha": ref, "per_page": per_page}
    )
    if response.status_code != 200:
        return []
    return response.json()