from datetime import datetime, timezone

from app.models import RepositoryMetrics
from app.services.grading import calculate_health_grade


def make_metrics(**overrides):
    defaults = {
        "owner": "fastapi",
        "name": "fastapi",
        "full_name": "fastapi/fastapi",
        "html_url": "https://github.com/fastapi/fastapi",
        "description": "FastAPI framework",
        "stars": 80000,
        "forks": 7000,
        "open_issues": 20,
        "open_prs": 5,
        "default_branch": "master",
        "language": "Python",
        "license": "MIT",
        "created_at": datetime(2018, 1, 1, tzinfo=timezone.utc),
        "pushed_at": datetime.now(timezone.utc),
        "latest_commit_at": datetime.now(timezone.utc),
        "age_days": 2000,
        "days_since_activity": 3,
        "archived": False,
        "disabled": False,
    }
    defaults.update(overrides)
    return RepositoryMetrics(**defaults)


def test_recent_mature_repository_with_small_backlog_gets_high_grade():
    grade = calculate_health_grade(make_metrics())

    assert grade.grade == "A"
    assert grade.score >= 85
    assert len(grade.reasons) == 3


def test_stale_repository_is_penalized():
    grade = calculate_health_grade(make_metrics(days_since_activity=900))

    assert grade.grade in {"D", "F"}


def test_high_open_issue_repository_is_penalized():
    grade = calculate_health_grade(make_metrics(open_issues=2000, days_since_activity=120))

    assert grade.grade in {"C", "D", "F"}
    assert any("open issue" in reason.lower() for reason in grade.reasons)


def test_very_new_repository_has_limited_history_penalty():
    grade = calculate_health_grade(make_metrics(age_days=10, open_issues=2, days_since_activity=1))

    assert grade.score < 90
    assert any("very new" in reason.lower() for reason in grade.reasons)
