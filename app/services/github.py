import os
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from app.models import RepositoryMetrics


GITHUB_API_BASE_URL = "https://api.github.com"
GITHUB_API_VERSION = "2022-11-28"
REPO_PART_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+$")


class InvalidGitHubUrlError(ValueError):
    """Raised when a URL cannot be parsed as a public GitHub repository URL."""


class GitHubApiError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def parse_github_url(repo_url: str) -> tuple[str, str]:
    cleaned = repo_url.strip()
    if not cleaned:
        raise InvalidGitHubUrlError("Please enter a GitHub repository URL.")

    if not cleaned.startswith(("http://", "https://")):
        cleaned = f"https://{cleaned}"

    parsed = urlparse(cleaned)
    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    if host != "github.com":
        raise InvalidGitHubUrlError("Please enter a public GitHub repository URL.")

    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 2:
        raise InvalidGitHubUrlError("GitHub URL must include an owner and repository name.")

    owner = parts[0]
    repo = parts[1].removesuffix(".git")

    if not REPO_PART_PATTERN.match(owner) or not REPO_PART_PATTERN.match(repo):
        raise InvalidGitHubUrlError("GitHub URL contains invalid owner or repository characters.")

    return owner, repo


async def fetch_repository_metrics(repo_url: str) -> RepositoryMetrics:
    owner, repo = parse_github_url(repo_url)
    headers = _github_headers()

    timeout = httpx.Timeout(12.0, connect=5.0)
    async with httpx.AsyncClient(
        base_url=GITHUB_API_BASE_URL,
        headers=headers,
        timeout=timeout,
        follow_redirects=True,
    ) as client:
        repo_response = await client.get(f"/repos/{owner}/{repo}")
        _raise_for_github_error(repo_response, owner, repo)
        repo_data = repo_response.json()

        default_branch = repo_data.get("default_branch") or "main"
        commits_response = await client.get(
            f"/repos/{owner}/{repo}/commits",
            params={"per_page": 1, "sha": default_branch},
        )
        
        prs_response = await client.get(
            f"/repos/{owner}/{repo}/pulls",
            params={"state": "open", "per_page": 1},
        )

    latest_commit_at = _extract_latest_commit_date(commits_response, owner, repo)
    _raise_for_github_error(prs_response, owner, repo)
    
    link_header = prs_response.headers.get("link")
    last_page = _extract_last_page(link_header)
    if last_page is not None:
        open_prs = last_page
    else:
        open_prs = len(prs_response.json())

    open_issues_count = int(repo_data.get("open_issues_count") or 0)
    open_issues = max(open_issues_count - open_prs, 0)

    now = datetime.now(timezone.utc)
    created_at = _parse_github_datetime(repo_data["created_at"])
    pushed_at = _parse_github_datetime(repo_data.get("pushed_at"))
    activity_date = latest_commit_at or pushed_at
    license_data = repo_data.get("license") or {}

    return RepositoryMetrics(
        owner=owner,
        name=repo_data.get("name") or repo,
        full_name=repo_data.get("full_name") or f"{owner}/{repo}",
        html_url=repo_data.get("html_url") or f"https://github.com/{owner}/{repo}",
        description=repo_data.get("description"),
        stars=int(repo_data.get("stargazers_count") or 0),
        forks=int(repo_data.get("forks_count") or 0),
        open_issues=open_issues,
        open_prs=open_prs,
        default_branch=default_branch,
        language=repo_data.get("language"),
        license=license_data.get("spdx_id") or license_data.get("name"),
        created_at=created_at,
        pushed_at=pushed_at,
        latest_commit_at=latest_commit_at,
        age_days=max((now - created_at).days, 0),
        days_since_activity=max((now - activity_date).days, 0) if activity_date else None,
        archived=bool(repo_data.get("archived")),
        disabled=bool(repo_data.get("disabled")),
    )


def _extract_last_page(link_header: str | None) -> int | None:
    if not link_header:
        return None
    pattern = r'<([^>]+)>;\s*rel=["\']last["\']'
    match = re.search(pattern, link_header)
    if match:
        url = match.group(1)
        page_match = re.search(r'[?&]page=(\d+)', url)
        if page_match:
            return int(page_match.group(1))
    return None


def _github_headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
        "User-Agent": "github-vitals-monitor",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _raise_for_github_error(response: httpx.Response, owner: str, repo: str) -> None:
    if response.status_code < 400:
        return

    if response.status_code == 404:
        raise GitHubApiError(
            404,
            f"We could not find {owner}/{repo}. Make sure the repository is public and the URL is correct.",
        )
    if response.status_code == 403:
        raise GitHubApiError(
            429,
            "GitHub rate limit reached. Add a GITHUB_TOKEN environment variable or try again later.",
        )
    if response.status_code == 401:
        raise GitHubApiError(401, "GitHub rejected the configured token. Please check GITHUB_TOKEN.")

    raise GitHubApiError(
        502,
        "GitHub is not responding as expected right now. Please try again in a moment.",
    )


def _extract_latest_commit_date(response: httpx.Response, owner: str, repo: str) -> datetime | None:
    if response.status_code == 409:
        return None
    _raise_for_github_error(response, owner, repo)

    commits: list[dict[str, Any]] = response.json()
    if not commits:
        return None

    commit = commits[0].get("commit") or {}
    committer = commit.get("committer") or {}
    author = commit.get("author") or {}
    return _parse_github_datetime(committer.get("date") or author.get("date"))


def _parse_github_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))
