import requests
import os
from dotenv import load_dotenv

load_dotenv()

GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET")

GITHUB_TIMEOUT = (5, 30)

def get_github_auth_url(state: str) -> str:
    return f"https://github.com/login/oauth/authorize?client_id={GITHUB_CLIENT_ID}&scope=repo&state={state}"

def exchange_code_for_token(code: str) -> str:
    response = requests.post(
        "https://github.com/login/oauth/access_token",
        headers={"Accept": "application/json"},
        json={
            "client_id": GITHUB_CLIENT_ID,
            "client_secret": GITHUB_CLIENT_SECRET,
            "code": code
        },
        timeout=GITHUB_TIMEOUT,
    )
    return response.json().get("access_token")

def get_user_repos(access_token: str) -> list:
    response = requests.get(
        "https://api.github.com/user/repos",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        timeout=GITHUB_TIMEOUT,
    )
    return response.json()

def get_user_info(access_token: str) -> dict:
    response = requests.get(
        "https://api.github.com/user",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        timeout=GITHUB_TIMEOUT,
    )
    return response.json()

def create_webhook(access_token: str, repo_full_name: str, webhook_url: str) -> dict:
    # If a webhook secret is configured, tell GitHub to sign every payload with it.
    # GitHub then sends an X-Hub-Signature-256 header we can verify on our side.

    config = {
        "url": webhook_url,
        "content_type": "json",
    }
    webhook_secret = os.getenv("GITHUB_WEBHOOK_SECRET")
    if webhook_secret:
        config["secret"] = webhook_secret
 
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
            "config": config,
        },
        timeout=GITHUB_TIMEOUT,
    )
    return response.json()

def get_file_content(access_token: str, repo_full_name: str, file_path: str, ref: str = "main") -> str:
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/contents/{file_path}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3.raw"
        },
        params={"ref": ref},
        timeout=GITHUB_TIMEOUT,
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
    response = requests.delete(url, headers=headers, timeout=GITHUB_TIMEOUT)
    return response.status_code == 204

def fetch_repo_branches(access_token: str, repo_full_name: str) -> list:
    """Fetch all branches of a repository (name + head commit sha)."""
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/branches",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        params={"per_page": 100},
        timeout=GITHUB_TIMEOUT,
    )
    if response.status_code != 200:
        return []
    return response.json()


def fetch_commits_for_ref(access_token: str, repo_full_name: str, ref: str, per_page: int = 100, max_pages: int = 50) -> list:
    """Fetch ALL commits reachable from a ref, paginating through pages."""
    all_commits = []
    page = 1
    while page <= max_pages:
        response = requests.get(
            f"https://api.github.com/repos/{repo_full_name}/commits",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json"
            },
            params={"sha": ref, "per_page": per_page, "page": page},
            timeout=GITHUB_TIMEOUT,
        )
        if response.status_code != 200:
            break
        batch = response.json()
        if not batch:
            break
        all_commits.extend(batch)
        if len(batch) < per_page:
            break   # last page
        page += 1
    return all_commits

def fetch_commit_files(access_token: str, repo_full_name: str, sha: str) -> list:
    """Return the files changed in a single commit (each with a 'status')."""
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}/commits/{sha}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        timeout=GITHUB_TIMEOUT,
    )
    if response.status_code != 200:
        return []
    return response.json().get("files", [])


def fetch_default_branch(access_token: str, repo_full_name: str) -> str:
    """Return the repository's default branch name (e.g. 'main')."""
    response = requests.get(
        f"https://api.github.com/repos/{repo_full_name}",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/vnd.github.v3+json"
        },
        timeout=GITHUB_TIMEOUT,
    )
    if response.status_code != 200:
        return None
    return response.json().get("default_branch")