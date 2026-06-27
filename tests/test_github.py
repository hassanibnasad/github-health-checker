import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from app.services.github import InvalidGitHubUrlError, fetch_repository_metrics, parse_github_url


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://github.com/fastapi/fastapi", ("fastapi", "fastapi")),
        ("github.com/tiangolo/fastapi.git", ("tiangolo", "fastapi")),
        ("https://github.com/pallets/flask/tree/main", ("pallets", "flask")),
    ],
)
def test_parse_github_url_accepts_common_repo_urls(url, expected):
    assert parse_github_url(url) == expected


@pytest.mark.parametrize(
    "url",
    [
        "",
        "https://gitlab.com/example/repo",
        "https://github.com/only-owner",
        "not a url",
    ],
)
def test_parse_github_url_rejects_invalid_urls(url):
    with pytest.raises(InvalidGitHubUrlError):
        parse_github_url(url)


def test_fetch_repository_metrics_uses_only_repo_commits_and_pulls_endpoints(monkeypatch):
    calls = []

    class FakeAsyncClient:
        def __init__(self, **_):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_):
            return None

        async def get(self, path, params=None):
            calls.append((path, params or {}))
            request = httpx.Request("GET", f"https://api.github.com{path}")
            if path == "/repos/fastapi/fastapi":
                return httpx.Response(
                    200,
                    json={
                        "name": "fastapi",
                        "full_name": "fastapi/fastapi",
                        "html_url": "https://github.com/fastapi/fastapi",
                        "description": "FastAPI framework",
                        "stargazers_count": 80000,
                        "forks_count": 7000,
                        "open_issues_count": 20,
                        "default_branch": "master",
                        "language": "Python",
                        "license": {"spdx_id": "MIT"},
                        "created_at": "2018-01-01T00:00:00Z",
                        "pushed_at": "2026-01-01T00:00:00Z",
                        "archived": False,
                        "disabled": False,
                    },
                    request=request,
                )
            if path == "/repos/fastapi/fastapi/commits":
                return httpx.Response(
                    200,
                    json=[{"commit": {"committer": {"date": datetime.now(timezone.utc).isoformat()}}}],
                    request=request,
                )
            if path == "/repos/fastapi/fastapi/pulls":
                return httpx.Response(
                    200,
                    json=[{}],
                    headers={"link": '<https://api.github.com/repositories/251007874/pulls?state=open&per_page=1&page=12>; rel="last"'},
                    request=request,
                )
            return httpx.Response(500, json={}, request=request)

    monkeypatch.setattr("app.services.github.httpx.AsyncClient", FakeAsyncClient)

    metrics = asyncio.run(fetch_repository_metrics("https://github.com/fastapi/fastapi"))

    assert metrics.full_name == "fastapi/fastapi"
    assert metrics.open_issues == 8
    assert metrics.open_prs == 12
    assert len(calls) == 3
    assert calls[0][0] == "/repos/fastapi/fastapi"
    assert calls[1][0] == "/repos/fastapi/fastapi/commits"
    assert calls[2][0] == "/repos/fastapi/fastapi/pulls"
    assert not any("search" in path for path, _ in calls)
