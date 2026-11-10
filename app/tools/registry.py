"""Tool definitions the model sees, and the dispatcher that runs them."""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from . import invoices, library, quality, sales

# The bakery tools are no longer shown to the model. Their code stays until the
# digest and the Invoices screen are replaced (step 6), then it is removed.
BAKERY_TOOLS: list[dict[str, Any]] = [
    {
        "name": "sales_query",
        "description": (
            "Read-only query over the bakery's sales lines (one row per product per order). "
            "Use it for any question about revenue, items sold, order counts, best sellers, branches, "
            "channels or trends. Pick a metric and a grouping; filter by date range (YYYY-MM-DD), branch, "
            "product or category. Refunded lines are excluded unless include_refunded is true. "
            "Never guess numbers: if the answer needs data, call this tool."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "metric": {"type": "string", "enum": sorted(sales.METRICS), "description": "revenue (ILS), items (units), orders (distinct orders) or avg_order (revenue per order)."},
                "group_by": {"type": "string", "enum": sorted(sales.GROUP_BY), "description": "none for a single total; product/branch/... for a ranking; day/week/month for a trend."},
                "date_from": {"type": "string", "description": "inclusive start date YYYY-MM-DD"},
                "date_to": {"type": "string", "description": "inclusive end date YYYY-MM-DD"},
                "branch": {"type": "string", "description": "substring match on branch name"},
                "product": {"type": "string", "description": "substring match on product name"},
                "category": {"type": "string", "description": "substring match on category (Bread, Pastry, Drinks, Sweet, ...)"},
                "include_refunded": {"type": "boolean", "default": False},
                "top_n": {"type": "integer", "minimum": 1, "maximum": 50, "default": 10},
            },
            "required": ["metric", "group_by"],
            "additionalProperties": False,
        },
    },
    {
        "name": "lookup_supplier",
        "description": "Look up a supplier by (partial) name in the bakery's supplier list. Returns the canonical name and the items and usual prices we buy from them. Call it before logging an invoice to normalise the supplier name.",
        "input_schema": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "supplier name as written on the invoice"}},
            "required": ["name"],
            "additionalProperties": False,
        },
    },
    {
        "name": "log_invoice",
        "description": (
            "Record one supplier invoice as one row. Pass the fields exactly as read from the document; "
            "pass amount as null if you cannot read it with confidence, and the row will be marked needs_a_look. "
            "Always pass source_ref (the image reference given in the message) so the same invoice is never logged twice. "
            "Never call this to modify or delete an existing row."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "supplier": {"type": "string"},
                "invoice_number": {"type": ["string", "null"]},
                "amount": {"type": ["number", "null"], "description": "total amount, numbers only; null if unreadable"},
                "currency": {"type": "string", "default": "ILS"},
                "invoice_date": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                "source_ref": {"type": ["string", "null"], "description": "the image reference from the message, e.g. img_8f3a2c"},
                "notes": {"type": ["string", "null"]},
            },
            "required": ["supplier", "amount"],
            "additionalProperties": False,
        },
    },
]

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
        if name == "sales_query":
            result = sales.sales_query(db, **_clean(tool_input))
        elif name == "lookup_supplier":
            result = invoices.lookup_supplier(db, name=str(tool_input.get("name", "")))
        elif name == "log_invoice":
            result = invoices.log_invoice(db, logged_by=user_id, **_clean(tool_input))
        elif name == "check_text":
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
