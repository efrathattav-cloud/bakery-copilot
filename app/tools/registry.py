"""Tool definitions the model sees, and the dispatcher that runs them."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from . import library, quality

# What the model sees.
TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_text",
        "description": (
            "Mechanical brand-voice check of a Hebrew text: long dashes, banned phrases and openings, "
            "too many exclamation marks or questions, emoji outside the allowed list, and length for the format. "
            "Call it on every draft before you show it, and on any text the user asks you to review. "
            "It does not judge tone or meaning; that stays with you."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "the full text to check, exactly as it would be published"},
                "format": {"type": "string", "enum": quality.FORMATS, "description": "community (group message), reply (to a participant), post, marketing, recording (text with a voice note), exercise, or other"},
            },
            "required": ["text"],
            "additionalProperties": False,
        },
    },
    {
        "name": "save_content",
        "description": (
            "Save one text to her content library. Call it only when she asks to keep a text "
            "('תשמור', 'שמרי את זה') or tells you she published it ('פרסמתי'). Never save drafts on your own. "
            "Save the final text exactly as agreed, with a short Hebrew topic of a few words."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "the full text, exactly as she approved it"},
                "topic": {"type": "string", "description": "a few words in Hebrew, e.g. 'הפחד לאכזב'"},
                "format": {"type": "string", "enum": quality.FORMATS},
                "status": {"type": "string", "enum": list(library.STATUSES), "description": "published if she says she posted it, otherwise draft"},
            },
            "required": ["text", "topic"],
            "additionalProperties": False,
        },
    },
    {
        "name": "mark_published",
        "description": (
            "Mark a text that is already in her library as published. Use it when she says she posted a text "
            "that was saved earlier as a draft, instead of saving it again. Find its id with search_content first."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"id": {"type": "integer", "description": "the library item id from search_content"}},
            "required": ["id"],
            "additionalProperties": False,
        },
    },
    {
        "name": "search_content",
        "description": (
            "Search her content library: what she already wrote, on which topic, when. "
            "Use it for questions like 'על מה כתבתי החודש?' or 'מתי כתבתי על אשמה?', and before drafting "
            "to see whether she wrote on the topic recently. Matches the query in the topic or the text. "
            "Returns newest first, with a preview of each text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "a word or phrase in Hebrew; omit to list everything"},
                "format": {"type": "string", "enum": quality.FORMATS},
                "status": {"type": "string", "enum": list(library.STATUSES)},
                "date_from": {"type": "string", "description": "inclusive start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "inclusive end date YYYY-MM-DD"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "additionalProperties": False,
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOLS}
MAX_RESULT_CHARS = 12000


def execute(name: str, tool_input: dict[str, Any], db: Session, *, user_id: int | None = None) -> str:
    """Run one tool and return its result as a JSON string for the model."""
    try:
        if name == "check_text":
            result = quality.check_text(str(tool_input.get("text", "")), str(tool_input.get("format") or "other"))
        elif name == "save_content":
            result = library.save_content(db, saved_by=user_id, **_clean(tool_input))
        elif name == "mark_published":
            result = library.mark_published(db, id=tool_input.get("id", 0))
        elif name == "search_content":
            result = library.search_content(db, **_clean(tool_input))
        else:
            result = {"error": f"unknown tool '{name}'"}
    except Exception as exc:  # the loop must survive a bad input; the model sees the error
        result = {"error": f"{type(exc).__name__}: {exc}"}
    text = json.dumps(result, ensure_ascii=False, default=str)
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + '... (truncated)"}'
    return text


def _clean(d: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in d.items() if v is not None}
