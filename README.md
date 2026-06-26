# GitHub Vitals Monitor

A simple FastAPI app that checks whether a public GitHub repository looks active, maintained, and safe to evaluate for production use.

The app chains two things interviewers care about:

- Hard data from the GitHub REST API.
- A short NVIDIA MiniMax verdict generated from those exact metrics.

The final grade is deterministic Python business logic. The AI explains the result, but it does not decide the grade.

## Features

- Paste a GitHub repository URL and get a dashboard.
- Uses only two GitHub API calls per scan: repository metadata and latest commit.
- Fetches stars, forks, open issues, latest commit activity, age, language, license, and archived status.
- Calculates a health grade from `A` to `F` using open issue count, repository age, and latest commit activity.
- Shows 3 plain-English grade reasons.
- Uses NVIDIA MiniMax through the OpenAI-compatible API.
- Falls back to a deterministic summary if `NVIDIA_API_KEY` is missing or the AI call fails.
- Includes Swagger docs at `/docs`.

## Tech Stack

- Backend: FastAPI, Pydantic, httpx.
- AI: NVIDIA NIM MiniMax M2.7 via the `openai` Python client.
- Frontend: Vanilla HTML, Tailwind CDN, and JavaScript.
- Tests: pytest.

## Local Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
uvicorn app.main:app --reload --reload-dir app
```

Open `http://127.0.0.1:8000`.

## Environment Variables

```bash
NVIDIA_API_KEY=your_nvidia_api_key_here
GITHUB_TOKEN=optional_github_personal_access_token
```

`GITHUB_TOKEN` is optional, but useful because unauthenticated GitHub requests hit rate limits quickly.

## API

```http
POST /api/health-check
Content-Type: application/json

{
  "repo_url": "https://github.com/fastapi/fastapi"
}
```

Useful routes:

- `/` for the dashboard.
- `/docs` for Swagger UI.
- `/health` for deployment health checks.

## GitHub Calls Per Scan

The backend intentionally avoids GitHub Search API throttling. Each repository scan uses only:

- `GET /repos/{owner}/{repo}`
- `GET /repos/{owner}/{repo}/commits?per_page=1&sha={default_branch}`

## Health Grade Explanation

The score is out of 100:

- Latest commit activity: up to 50 points.
- Open issue count: up to 30 points.
- Repository age: up to 20 points.

The grade does not use GitHub Search API data, closed issue counts, stars, or forks. Stars and forks are displayed as context only.

## Render Deployment

This repository includes a [render.yaml](file:///c:/Users/DELL/OneDrive/Desktop/Code/github-health-checker/render.yaml) file config for simple native Python web service deployments on Render.

### Deployment steps:
1. Push your repository to GitHub.
2. Link your repository to a new **Web Service** in the Render Dashboard.
3. Configure the service:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Add the following **Environment Variables** in Render settings:
   - `NVIDIA_API_KEY`: Your Nvidia API Key.
   - `GITHUB_TOKEN` *(Optional)*: Your GitHub personal access token (recommended to prevent API rate limits).
