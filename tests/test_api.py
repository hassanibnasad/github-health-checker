from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.models import AIVerdict, RepositoryMetrics
from app.services.github import GitHubApiError


client = TestClient(app)


def make_metrics() -> RepositoryMetrics:
    return RepositoryMetrics(
        owner="fastapi",
        name="fastapi",
        full_name="fastapi/fastapi",
        html_url="https://github.com/fastapi/fastapi",
        description="FastAPI framework",
        stars=80000,
        forks=7000,
        open_issues=20,
        open_prs=5,
        default_branch="master",
        language="Python",
        license="MIT",
        created_at=datetime(2018, 1, 1, tzinfo=timezone.utc),
        pushed_at=datetime.now(timezone.utc),
        latest_commit_at=datetime.now(timezone.utc),
        age_days=2000,
        days_since_activity=2,
        archived=False,
        disabled=False,
    )


def test_health_endpoint():
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_check_returns_expected_shape(monkeypatch):
    async def fake_fetch_repository_metrics(_):
        return make_metrics()

    async def fake_generate_ai_summary(_, __):
        return AIVerdict(
            summary="Looks healthy. Maintenance is active. Adoption risk is low.",
            provider="test",
            model="test",
            reasons=["AI reason 1", "AI reason 2", "AI reason 3"]
        )

    monkeypatch.setattr("app.main.fetch_repository_metrics", fake_fetch_repository_metrics)
    monkeypatch.setattr("app.main.generate_ai_summary", fake_generate_ai_summary)

    response = client.post("/api/health-check", json={"repo_url": "https://github.com/fastapi/fastapi"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["repository"]["full_name"] == "fastapi/fastapi"
    assert payload["repository"]["open_issues"] == 20
    assert "closed_issues" not in payload["repository"]
    assert payload["health"]["grade"] == "A"
    assert payload["ai_verdict"]["summary"].startswith("Looks healthy")


def test_broken_repo_url_returns_polite_400():
    response = client.post("/api/health-check", json={"repo_url": "not a url"})

    assert response.status_code == 400
    assert "GitHub" in response.json()["detail"]


def test_github_404_returns_polite_error(monkeypatch):
    async def fake_fetch_repository_metrics(_):
        raise GitHubApiError(404, "We could not find example/missing.")

    monkeypatch.setattr("app.main.fetch_repository_metrics", fake_fetch_repository_metrics)

    response = client.post("/api/health-check", json={"repo_url": "https://github.com/example/missing"})

    assert response.status_code == 404
    assert "could not find" in response.json()["detail"].lower()


def test_github_403_returns_rate_limit_friendly_error(monkeypatch):
    async def fake_fetch_repository_metrics(_):
        raise GitHubApiError(429, "GitHub rate limit reached.")

    monkeypatch.setattr("app.main.fetch_repository_metrics", fake_fetch_repository_metrics)

    response = client.post("/api/health-check", json={"repo_url": "https://github.com/fastapi/fastapi"})

    assert response.status_code == 429
    assert "rate limit" in response.json()["detail"].lower()
