"""LinkedIn post generation via Gemini (OpenAI → Claude fallback chain, offline mock)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ..config import settings
from .brand import BRAND_BRIEF, FORMAT_GUIDE, POST_FORMATS

log = logging.getLogger(__name__)


@dataclass
class GeneratedPost:
    headline: str
    body: str
    format_type: str
    hashtags: list[str] = field(default_factory=list)
    image_recommended: bool = False
    image_reason: str = ""
    image_query: str = ""


# Structured-output contract Claude must fill via forced tool use.
_DRAFT_TOOL = {
    "name": "draft_linkedin_post",
    "description": "Return a finished LinkedIn post draft for QuantrixLabs.",
    "input_schema": {
        "type": "object",
        "properties": {
            "format_type": {
                "type": "string",
                "enum": list(POST_FORMATS.keys()),
                "description": "The single best format for this story.",
            },
            "headline": {
                "type": "string",
                "description": "A short internal label for this post (the angle), "
                               "max ~80 chars. Not shown in the post body.",
            },
            "body": {
                "type": "string",
                "description": "The full LinkedIn post text, ready to publish. "
                               "Under 3000 characters. Do NOT include hashtags "
                               "here; they are returned separately.",
            },
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "3-6 relevant hashtags WITHOUT the # symbol. "
                               "Include CyberSecurity and QuantrixLabs.",
            },
            "image_recommended": {
                "type": "boolean",
                "description": "Whether a supporting image would strengthen this "
                               "specific post on LinkedIn.",
            },
            "image_reason": {
                "type": "string",
                "description": "One sentence explaining the image recommendation.",
            },
            "image_query": {
                "type": "string",
                "description": "If recommended, a concrete visual stock-photo "
                               "search query (non-branded). Else empty string.",
            },
        },
        "required": [
            "format_type", "headline", "body", "hashtags",
            "image_recommended", "image_reason", "image_query",
        ],
    },
}


def _build_user_prompt(cand) -> str:
    article = cand.full_text or cand.summary or ""
    return f"""\
Here is today's news story to turn into a {", ".join(POST_FORMATS)} style post.

AVAILABLE FORMATS (choose exactly one):
{FORMAT_GUIDE}

STORY SOURCE: {cand.source_name}
HEADLINE: {cand.title}
URL: {cand.url}

ARTICLE TEXT:
\"\"\"
{article[:7000]}
\"\"\"

Write the QuantrixLabs post now using the draft_linkedin_post tool. Remember: \
general public, plain language, hook first, truth only from the article above, \
end with engagement.
"""


def _normalize_hashtags(tags: list[str]) -> list[str]:
    seen, out = set(), []
    for t in tags:
        clean = t.lstrip("#").strip().replace(" ", "")
        if clean and clean.lower() not in seen:
            seen.add(clean.lower())
            out.append(clean)
    for required in ("CyberSecurity", "QuantrixLabs"):
        if required.lower() not in {x.lower() for x in out}:
            out.append(required)
    return out[:6]


def _generate_with_gemini(cand) -> GeneratedPost:
    import json
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=settings.gemini_api_key)
    schema = _DRAFT_TOOL["input_schema"]
    # Build Gemini function declaration from the shared schema.
    fn = types.FunctionDeclaration(
        name=_DRAFT_TOOL["name"],
        description=_DRAFT_TOOL["description"],
        parameters=schema,
    )
    config = types.GenerateContentConfig(
        system_instruction=BRAND_BRIEF,
        tools=[types.Tool(function_declarations=[fn])],
        tool_config=types.ToolConfig(
            function_calling_config=types.FunctionCallingConfig(
                mode="ANY",
                allowed_function_names=[_DRAFT_TOOL["name"]],
            )
        ),
        max_output_tokens=2000,
    )
    resp = client.models.generate_content(
        model=settings.gemini_model,
        contents=_build_user_prompt(cand),
        config=config,
    )
    call = resp.candidates[0].content.parts[0].function_call
    # Gemini returns a MapComposite — convert to plain dict.
    data = dict(call.args)
    return GeneratedPost(
        headline=str(data["headline"]).strip(),
        body=str(data["body"]).strip(),
        format_type=str(data["format_type"]),
        hashtags=_normalize_hashtags(list(data.get("hashtags", []))),
        image_recommended=bool(data["image_recommended"]),
        image_reason=str(data.get("image_reason", "")).strip(),
        image_query=str(data.get("image_query", "")).strip(),
    )


def _generate_with_openai(cand) -> GeneratedPost:
    import json
    import openai

    client = openai.OpenAI(api_key=settings.openai_api_key)
    # Convert the Anthropic tool schema to OpenAI function format.
    fn = {
        "type": "function",
        "function": {
            "name": _DRAFT_TOOL["name"],
            "description": _DRAFT_TOOL["description"],
            "parameters": _DRAFT_TOOL["input_schema"],
        },
    }
    resp = client.chat.completions.create(
        model=settings.openai_model,
        max_tokens=2000,
        messages=[
            {"role": "system", "content": BRAND_BRIEF},
            {"role": "user", "content": _build_user_prompt(cand)},
        ],
        tools=[fn],
        tool_choice={"type": "function", "function": {"name": "draft_linkedin_post"}},
    )
    args = resp.choices[0].message.tool_calls[0].function.arguments
    data = json.loads(args)
    return GeneratedPost(
        headline=data["headline"].strip(),
        body=data["body"].strip(),
        format_type=data["format_type"],
        hashtags=_normalize_hashtags(data.get("hashtags", [])),
        image_recommended=bool(data["image_recommended"]),
        image_reason=data.get("image_reason", "").strip(),
        image_query=data.get("image_query", "").strip(),
    )


def _generate_with_claude(cand) -> GeneratedPost:
    import anthropic

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    resp = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=2000,
        system=BRAND_BRIEF,
        tools=[_DRAFT_TOOL],
        tool_choice={"type": "tool", "name": "draft_linkedin_post"},
        messages=[{"role": "user", "content": _build_user_prompt(cand)}],
    )
    tool_use = next(b for b in resp.content if b.type == "tool_use")
    data = tool_use.input
    return GeneratedPost(
        headline=data["headline"].strip(),
        body=data["body"].strip(),
        format_type=data["format_type"],
        hashtags=_normalize_hashtags(data.get("hashtags", [])),
        image_recommended=bool(data["image_recommended"]),
        image_reason=data.get("image_reason", "").strip(),
        image_query=data.get("image_query", "").strip(),
    )


def _generate_mock(cand) -> GeneratedPost:
    """Deterministic offline draft so the pipeline is testable without a key."""
    snippet = (cand.summary or cand.full_text or "").strip()
    snippet = snippet[:240] + ("…" if len(snippet) > 240 else "")
    body = (
        f"Heads up: {cand.title}.\n\n"
        f"{snippet}\n\n"
        "Keep your software updated, use strong unique passwords, and turn on "
        "two-factor authentication wherever you can.\n\n"
        "What's the one security habit you keep putting off? 👇\n\n"
        f"(Source: {cand.source_name})"
    )
    return GeneratedPost(
        headline=cand.title[:80],
        body=body,
        format_type="explainer",
        hashtags=_normalize_hashtags(["OnlineSafety", "InfoSec"]),
        image_recommended=True,
        image_reason="A relatable human image helps a general audience connect "
                     "with an abstract security topic.",
        image_query="person using laptop and phone at home",
    )


_TONE_GUIDE = {
    "punchy": "Make it punchier and more energetic: shorter sentences, a "
              "stronger scroll-stopping hook, more momentum. Keep all facts.",
    "formal": "Make it more measured and professional in tone, while staying "
              "accessible to a general audience. Keep all facts.",
    "shorter": "Tighten it: cut filler, keep only the strongest lines and the "
               "takeaway. Keep all facts.",
}


def rephrase_body(body: str, tone: str) -> str:
    """Rephrase a post body in a given tone. Uses Gemini → OpenAI → Claude fallback."""
    guide = _TONE_GUIDE.get(tone, _TONE_GUIDE["punchy"])
    prompt = (
        f"{guide}\n\nRewrite this LinkedIn post. Return ONLY the "
        f"rewritten post text, no preamble:\n\n{body}"
    )
    if settings.has_gemini:
        try:
            from google import genai
            from google.genai import types
            client = genai.Client(api_key=settings.gemini_api_key)
            resp = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=BRAND_BRIEF,
                    max_output_tokens=1500,
                ),
            )
            text = resp.text.strip() if resp.text else ""
            return text or body
        except Exception as exc:
            log.error("Gemini rephrase failed: %s", exc)
    if settings.has_openai:
        try:
            import openai
            client = openai.OpenAI(api_key=settings.openai_api_key)
            resp = client.chat.completions.create(
                model=settings.openai_model,
                max_tokens=1500,
                messages=[
                    {"role": "system", "content": BRAND_BRIEF},
                    {"role": "user", "content": prompt},
                ],
            )
            text = (resp.choices[0].message.content or "").strip()
            return text or body
        except Exception as exc:
            log.error("OpenAI rephrase failed: %s", exc)
    if settings.has_anthropic:
        try:
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            resp = client.messages.create(
                model=settings.anthropic_model,
                max_tokens=1500,
                system=BRAND_BRIEF,
                messages=[{"role": "user", "content": prompt}],
            )
            text = "".join(b.text for b in resp.content if b.type == "text").strip()
            return text or body
        except Exception as exc:
            log.error("Claude rephrase failed: %s", exc)
    # Mock: trivial deterministic nudge so the UI flow is testable.
    prefix = {"punchy": "🔥 ", "formal": "", "shorter": ""}.get(tone, "")
    return prefix + body


def generate_post(cand) -> GeneratedPost:
    if settings.has_gemini:
        try:
            return _generate_with_gemini(cand)
        except Exception as exc:
            log.error("Gemini generation failed for %r, trying OpenAI: %s",
                      cand.title[:60], exc)
    if settings.has_openai:
        try:
            return _generate_with_openai(cand)
        except Exception as exc:
            log.error("OpenAI generation failed for %r, trying Claude: %s",
                      cand.title[:60], exc)
    if settings.has_anthropic:
        try:
            return _generate_with_claude(cand)
        except Exception as exc:
            log.error("Claude generation failed for %r, using mock: %s",
                      cand.title[:60], exc)
    log.info("No API key available — using mock generator.")
    return _generate_mock(cand)
