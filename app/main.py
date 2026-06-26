from datetime import datetime, timezone
from pathlib import Path

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from app.models import ErrorResponse, HealthCheckRequest, HealthCheckResponse
from app.services.ai import generate_ai_summary
from app.services.github import GitHubApiError, InvalidGitHubUrlError, fetch_repository_metrics
from app.services.grading import calculate_health_grade


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="GitHub Vitals Monitor",
    description="Analyze public GitHub repositories using GitHub metrics and an NVIDIA MiniMax verdict.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, __) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": "Please provide a valid GitHub repository URL."},
    )


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post(
    "/api/health-check",
    response_model=HealthCheckResponse,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        429: {"model": ErrorResponse},
        502: {"model": ErrorResponse},
        504: {"model": ErrorResponse},
    },
)
async def health_check(payload: HealthCheckRequest) -> HealthCheckResponse:
    try:
        metrics = await fetch_repository_metrics(payload.repo_url)
        health_grade = calculate_health_grade(metrics)
        ai_verdict = await generate_ai_summary(metrics, health_grade)
        health_grade.reasons = ai_verdict.reasons
        return HealthCheckResponse(
            repository=metrics,
            health=health_grade,
            ai_verdict=ai_verdict,
            checked_at=datetime.now(timezone.utc),
        )
    except InvalidGitHubUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except GitHubApiError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=504, detail="GitHub took too long to respond. Please try again.") from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail="Could not connect to GitHub right now.") from exc

