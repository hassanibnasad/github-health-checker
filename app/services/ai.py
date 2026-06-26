import json
import os

from openai import APIConnectionError, APIError, APITimeoutError, AsyncOpenAI

from app.models import AIVerdict, HealthGrade, RepositoryMetrics


NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"
NVIDIA_MODEL = "meta/llama-3.1-8b-instruct"


async def generate_ai_summary(metrics: RepositoryMetrics, health: HealthGrade) -> AIVerdict:
    api_key = os.getenv("NVIDIA_API_KEY")
    if not api_key:
        return _fallback_verdict(metrics, health, "fallback")

    client = AsyncOpenAI(base_url=NVIDIA_BASE_URL, api_key=api_key)

    try:
        completion = await client.chat.completions.create(
            model=NVIDIA_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior engineer evaluating open-source repository health. "
                        "Respond ONLY with a valid JSON object. Do not wrap it in markdown block or write any text other than the raw JSON itself.\n"
                        "The JSON object must have exactly these keys:\n"
                        '{\n'
                        '  "summary": "exactly three sentences evaluating whether this repository is safe, active, and reliable to use.",\n'
                        '  "reasons": ["AI-generated reason 1", "AI-generated reason 2", "AI-generated reason 3"]\n'
                        '}\n'
                        "Write 3 short reasons explaining the grade based on the metrics, license, activity, and community adoption."
                    ),
                },
                {"role": "user", "content": _build_prompt(metrics, health)},
            ],
            temperature=0.2,
            max_tokens=512,
            stream=False,
        )
        raw_content = (completion.choices[0].message.content or "").strip()
        if not raw_content:
            return _fallback_verdict(metrics, health, "fallback")
        
        parsed = _parse_json_safely(raw_content)
        summary = parsed.get("summary", "").strip()
        reasons = parsed.get("reasons", [])
        
        if not summary or not isinstance(reasons, list) or len(reasons) == 0:
            return _fallback_verdict(metrics, health, "fallback")
            
        return AIVerdict(summary=summary, provider="nvidia", model=NVIDIA_MODEL, reasons=reasons)
    except (APIError, APIConnectionError, APITimeoutError, IndexError, AttributeError, ValueError, json.JSONDecodeError):
        return _fallback_verdict(metrics, health, "fallback")


def _parse_json_safely(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)



def _build_prompt(metrics: RepositoryMetrics, health: HealthGrade) -> str:
    return (
        f"Repository: {metrics.full_name}\n"
        f"Health grade: {health.grade} ({health.score}/100)\n"
        "The deterministic grade is based only on these three inputs:\n"
        f"Open issues: {metrics.open_issues}\n"
        f"Days since latest commit activity: {metrics.days_since_activity}\n"
        f"Repository age in days: {metrics.age_days}\n"
        "Additional context from the same repository endpoint:\n"
        f"Stars: {metrics.stars}\n"
        f"Forks: {metrics.forks}\n"
        f"Language: {metrics.language or 'unknown'}\n"
        f"License: {metrics.license or 'unknown'}\n"
        f"Archived: {metrics.archived}\n"
        f"Disabled: {metrics.disabled}\n"
        "Explain whether this repository looks safe and reliable to use."
    )


def _fallback_verdict(metrics: RepositoryMetrics, health: HealthGrade, provider: str) -> AIVerdict:
    activity = (
        "no recent activity data"
        if metrics.days_since_activity is None
        else f"activity {metrics.days_since_activity} days ago"
    )
    summary = (
        f"{metrics.full_name} receives a {health.grade} grade with a score of {health.score}/100. "
        f"The grade is based on {metrics.open_issues:,} open issues, "
        f"a repository age of {metrics.age_days:,} days, and {activity}. "
        "Review the grade reasons before adopting it in a production project."
    )
    return AIVerdict(summary=summary, provider=provider, model="deterministic-fallback", reasons=health.reasons)
