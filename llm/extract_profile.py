"""Structured vacancy profile extraction via OpenAI Responses API."""

from typing import Any, Dict, Optional
import os

from openai import OpenAI
from pydantic import BaseModel, Field
from tenacity import retry, wait_exponential_jitter, stop_after_attempt


class VacancyProfile(BaseModel):
    """Structured representation of a job vacancy."""

    title: str = ""
    company: str = ""
    location: str = ""
    employment_type: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    requirements: list[str] = Field(default_factory=list)
    nice_to_have: list[str] = Field(default_factory=list)
    salary: Optional[str] = ""
    work_policy: Optional[str] = ""
    skills_hard: list[str] = Field(default_factory=list)
    skills_soft: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


class ChatCallResult(BaseModel):
    """Return type for extraction calls."""

    ok: bool
    profile: VacancyProfile
    usage: Dict[str, Any] = Field(default_factory=dict)
    raw: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None


# Tenacity's type hints omit ``initial`` keyword.
_WAIT = wait_exponential_jitter(initial=1, max=8)


@retry(wait=_WAIT, stop=stop_after_attempt(3))
def extract_profile_from_text(jd_text: str, lang: str = "en") -> ChatCallResult:
    """Extract a :class:`VacancyProfile` from plain text.

    Args:
        jd_text: Raw job description text.
        lang: Language code of the text.

    Returns:
        ChatCallResult: Outcome of the API call with parsed profile.

    Raises:
        AssertionError: If ``jd_text`` is empty.
    """
    assert jd_text.strip(), "empty JD text"
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    model = os.environ.get("OPENAI_MODEL", "o4-mini")

    tool = {
        "type": "function",
        "function": {
            "name": "emit_profile",
            "description": "Return a structured vacancy profile extracted from the job description.",
            "parameters": VacancyProfile.model_json_schema(),
        },
    }

    prompt = f"""You extract structured vacancy data from raw job descriptions.
Return only via the provided function tool 'emit_profile'. Language: {lang}.
Text:
{jd_text}"""

    resp = client.responses.create(  # type: ignore[call-overload]
        model=model,
        input=prompt,
        tools=[tool],
        tool_choice={"type": "function", "function": {"name": "emit_profile"}},
        temperature=0.2,
    )

    fcall = None
    for item in resp.output if hasattr(resp, "output") else []:
        if (
            getattr(item, "type", "") == "tool_call"
            and item.tool_call.function.name == "emit_profile"
        ):
            fcall = item.tool_call
            break
    if (
        not fcall
        and hasattr(resp, "output")
        and len(resp.output)
        and getattr(resp.output[0], "type", "") == "tool_call"
    ):
        fcall = resp.output[0].tool_call

    if not fcall:
        return ChatCallResult(
            ok=False,
            profile=VacancyProfile(),
            error="No tool_call found",
            raw=resp.model_dump(),
        )

    args = fcall.function.arguments
    prof = VacancyProfile.model_validate(args)
    usage = getattr(resp, "usage", {}) or {}
    return ChatCallResult(ok=True, profile=prof, usage=usage, raw=resp.model_dump())
