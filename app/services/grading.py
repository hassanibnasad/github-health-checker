from app.models import HealthGrade, RepositoryMetrics


# The grade intentionally uses only cheap, non-search GitHub data:
# latest commit activity, open issue count, and repository age.
def calculate_health_grade(metrics: RepositoryMetrics) -> HealthGrade:
    activity_score, activity_reason = _score_activity(metrics.days_since_activity)
    issue_score, issue_reason = _score_open_issues(metrics.open_issues)
    age_score, age_reason = _score_age(metrics.age_days)

    score = activity_score + issue_score + age_score
    reasons = [activity_reason, issue_reason, age_reason]

    # Deductions:
    # 1. Archived or Disabled
    if metrics.archived or metrics.disabled:
        status_type = "archived" if metrics.archived else "disabled"
        score -= 40
        reasons.append(f"Repository is {status_type}, making it read-only and unmaintained.")

    # 2. No license
    if not metrics.license or metrics.license.strip().lower() in ("none", "unknown", "no license detected"):
        score -= 20
        reasons.append("No license detected. Lack of a license poses significant legal risks for production adoption.")

    # 3. Low community adoption
    if metrics.stars == 0 and metrics.forks == 0:
        score -= 15
        reasons.append("Zero stars and forks indicate minimal community adoption or vetting.")

    final_score = max(0, min(100, score))
    return HealthGrade(
        grade=_grade_from_score(final_score),
        score=final_score,
        reasons=reasons,
    )


def _score_activity(days_since_activity: int | None) -> tuple[int, str]:
    if days_since_activity is None:
        return 5, "No commit activity was found for the default branch."
    if days_since_activity <= 30:
        return 50, "Recently active within the last 30 days."
    if days_since_activity <= 90:
        return 42, "Maintained recently within the last 90 days."
    if days_since_activity <= 180:
        return 34, "Some activity in the last six months."
    if days_since_activity <= 365:
        return 24, "Activity is getting stale but still within the last year."
    if days_since_activity <= 730:
        return 12, "Repository activity is stale."
    return 0, "Repository appears inactive."


def _score_open_issues(open_issues: int) -> tuple[int, str]:
    if open_issues == 0:
        return 30, "No open issue backlog was found."
    if open_issues <= 25:
        return 27, f"Open issue backlog is small at {open_issues:,} issues."
    if open_issues <= 100:
        return 22, f"Open issue backlog is manageable at {open_issues:,} issues."
    if open_issues <= 500:
        return 15, f"Open issue backlog is elevated at {open_issues:,} issues."
    if open_issues <= 1000:
        return 8, f"Open issue backlog is high at {open_issues:,} issues."
    return 3, f"Open issue backlog is very high at {open_issues:,} issues."


def _score_age(age_days: int) -> tuple[int, str]:
    if age_days < 30:
        return 6, "Repository is very new, so reliability history is limited."
    if age_days < 180:
        return 12, "Repository is still young but has some public history."
    if age_days < 365:
        return 16, "Repository has several months of public history."
    return 20, "Repository has at least one year of public history."


def _grade_from_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 55:
        return "C"
    if score >= 40:
        return "D"
    return "F"
