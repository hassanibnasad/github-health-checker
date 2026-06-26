import asyncio
from datetime import datetime, timezone

import httpx
from openai import APITimeoutError

from app.models import RepositoryMetrics
from app.services.ai import generate_ai_summary
from app.services.grading import calculate_health_grade


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


def test_ai_summary_uses_fallback_when_key_is_missing(monkeypatch):
    monkeypatch.delenv("NVIDIA_API_KEY", raising=False)
    metrics = make_metrics()
    health = calculate_health_grade(metrics)

    verdict = asyncio.run(generate_ai_summary(metrics, health))

    assert verdict.provider == "fallback"
    assert verdict.model == "deterministic-fallback"
    assert "fastapi/fastapi" in verdict.summary


def test_ai_summary_uses_fallback_when_nvidia_call_fails(monkeypatch):
    class FakeCompletions:
        async def create(self, **_):
            request = httpx.Request("POST", "https://integrate.api.nvidia.com/v1/chat/completions")
            raise APITimeoutError(request=request)

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        def __init__(self, **_):
            self.chat = FakeChat()

    monkeypatch.setenv("NVIDIA_API_KEY", "test-key")
    monkeypatch.setattr("app.services.ai.AsyncOpenAI", FakeClient)
    metrics = make_metrics()
    health = calculate_health_grade(metrics)

    verdict = asyncio.run(generate_ai_summary(metrics, health))

    assert verdict.provider == "fallback"
    assert verdict.model == "deterministic-fallback"
    assert str(health.score) in verdict.summary
