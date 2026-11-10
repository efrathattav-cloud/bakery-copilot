"""The content library: save a text she chose to keep, and search what she already wrote."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ..db import ContentItem
from .quality import FORMATS

STATUSES = ("draft", "published")
PREVIEW_CHARS = 200


def save_content(db: Session, *, text: str, topic: str, format: str = "other", status: str = "draft",
                 saved_by: int | None = None) -> dict[str, Any]:
    text, topic = (text or "").strip(), (topic or "").strip()
    if not text:
        return {"error": "text is empty; nothing saved"}
    if not topic:
        return {"error": "topic is required (a few words, e.g. 'הפחד לאכזב')"}
    fmt = format if format in FORMATS else "other"
    status = status if status in STATUSES else "draft"
    item = ContentItem(text=text, topic=topic[:120], format=fmt, status=status, saved_by=saved_by)
    db.add(item)
    db.commit()
    return {"saved": True, "id": item.id, "topic": item.topic, "format": fmt, "status": status}


def mark_published(db: Session, *, id: int) -> dict[str, Any]:
    item = db.get(ContentItem, int(id))
    if item is None:
        return {"error": f"no library item with id {id}; search first to find the right id"}
    if item.status == "published":
        return {"already_published": True, "id": item.id, "topic": item.topic}
    item.status = "published"
    db.commit()
    return {"updated": True, "id": item.id, "topic": item.topic, "status": "published"}


def search_content(db: Session, *, query: str | None = None, format: str | None = None, status: str | None = None,
                   date_from: str | None = None, date_to: str | None = None, limit: int = 10) -> dict[str, Any]:
    stmt = select(ContentItem)
    if query:
        like = f"%{query.strip()}%"
        stmt = stmt.where(or_(ContentItem.topic.ilike(like), ContentItem.text.ilike(like)))
    if format:
        stmt = stmt.where(ContentItem.format == format)
    if status:
        stmt = stmt.where(ContentItem.status == status)
    if date_from:
        stmt = stmt.where(ContentItem.created_at >= datetime.combine(date.fromisoformat(date_from), datetime.min.time()))
    if date_to:
        stmt = stmt.where(ContentItem.created_at < datetime.combine(date.fromisoformat(date_to) + timedelta(days=1), datetime.min.time()))
    limit = max(1, min(int(limit or 10), 50))
    rows = db.scalars(stmt.order_by(ContentItem.created_at.desc()).limit(limit)).all()
    return {
        "count": len(rows),
        "items": [
            {
                "id": r.id,
                "date": r.created_at.date().isoformat(),
                "format": r.format,
                "status": r.status,
                "topic": r.topic,
                "preview": r.text if len(r.text) <= PREVIEW_CHARS else r.text[:PREVIEW_CHARS] + "…",
            }
            for r in rows
        ],
    }
