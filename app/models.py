from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class HealthCheckRequest(BaseModel):
    repo_url: str = Field(
        ...,
        min_length=8,
        examples=["https://github.com/fastapi/fastapi"],
    )

    @field_validator("repo_url")
    @classmethod
    def repo_url_must_not_be_blank(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Repository URL is required.")
        return cleaned


class RepositoryMetrics(BaseModel):
    owner: str
    name: str
    full_name: str
    html_url: str
    description: str | None = None
    stars: int
    forks: int
    open_issues: int
    default_branch: str
    language: str | None = None
    license: str | None = None
    created_at: datetime
    pushed_at: datetime | None = None
    latest_commit_at: datetime | None = None
    age_days: int
    days_since_activity: int | None = None
    archived: bool
    disabled: bool


class HealthGrade(BaseModel):
    grade: Literal["A", "B", "C", "D", "F"]
    score: int = Field(..., ge=0, le=100)
    reasons: list[str] = Field(default_factory=list)


class AIVerdict(BaseModel):
    summary: str
    provider: str
    model: str
    reasons: list[str] = Field(default_factory=list)


class HealthCheckResponse(BaseModel):
    repository: RepositoryMetrics
    health: HealthGrade
    ai_verdict: AIVerdict
    checked_at: datetime


class ErrorResponse(BaseModel):
    detail: str
