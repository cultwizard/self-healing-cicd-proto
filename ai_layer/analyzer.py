import json
import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.5-flash:generateContent"
)


async def analyze_failure(logs: str, git_diff: str) -> dict:
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        return {
            "root_cause": "GEMINI_API_KEY not configured — fallback diagnosis triggered.",
            "severity": "MEDIUM",
            "suggested_fix": "Inspect the failing test stack trace in the CI logs and fix the broken code.",
        }

    prompt = f"""You are a senior DevOps SRE. Analyze the failed CI/CD logs and git diff below.
Return ONLY valid JSON with these exact keys:
- "root_cause": concise string explaining why the deployment/test failed
- "severity": one of "LOW", "MEDIUM", "HIGH", "CRITICAL"
- "suggested_fix": markdown string containing the exact corrected code snippet

=== CI / RUNTIME LOGS ===
{logs[-4000:]}

=== GIT DIFF ===
{git_diff[:4000]}
"""

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            res = await client.post(f"{GEMINI_URL}?key={api_key}", json=payload)
            res.raise_for_status()
            raw_text = res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            if raw_text.startswith("```"):
                raw_text = raw_text.strip("`").lstrip("json").strip()
            parsed = json.loads(raw_text)
            return {
                "root_cause": parsed.get("root_cause", "Unknown root cause"),
                "severity": parsed.get("severity", "HIGH"),
                "suggested_fix": parsed.get("suggested_fix", "Manual review required."),
            }
    except Exception as exc:
        print(f"[AI Layer] Diagnosis error: {exc}")
        return {
            "root_cause": f"LLM diagnosis failed: {exc}",
            "severity": "HIGH",
            "suggested_fix": "Review the raw CI logs manually.",
        }
