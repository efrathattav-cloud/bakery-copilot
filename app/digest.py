"""The morning card: this week's pace, a topic she has not touched for a while, drafts waiting.

Built in plain code from the content library, no model call: it costs nothing
each morning and is testable. The app shows it on the empty chat screen
(GET /api/morning). `python -m app.digest` and POST /internal/digest print the
same card as text, and send it to DIGEST_WEBHOOK_URL if one is set.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .config import settings
from .db import ContentItem, Run, SessionLocal, init_db

# The core topics of her work (brand-voice guide §2, §9, §14, §16), each with the
# words that show a library text is about it, and an opening from guide §6.
TOPICS: list[dict] = [
    {"topic": "הפחד לאכזב", "words": ["לאכזב", "אכזבה"], "opening": "יש תופעה שאני רואה שוב ושוב..."},
    {"topic": "ריצוי", "words": ["ריצוי", "לרצות", "מרצה"], "opening": "יש הבחנה אחת שחשוב לי לשים עליה רגע אור."},
    {"topic": "אשמה", "words": ["אשמה", "אשמות"], "opening": "יש משפט שנכתב כאן ונשאר איתי."},
    {"topic": "הצורך באישור", "words": ["אישור"], "opening": "איפה את מרגישה שאת כבר יודעת, אבל עדיין מחכה לאישור?"},
    {"topic": "להציב גבול", "words": ["גבול", "גבולות"], "opening": "השבוע עלתה כאן נקודה שממש שווה להתעכב עליה."},
    {"topic": "לבחור בעצמי", "words": ["לבחור", "בחירה"], "opening": "אני רוצה לקחת רגע משהו שעלה כאן ולהסתכל עליו עוד שכבה פנימה."},
    {"topic": "חוסר ביטחון", "words": ["ביטחון"], "opening": "יש תופעה שאני רואה שוב ושוב..."},
    {"topic": "לדחות את מה שנכון לי", "words": ["לדחות", "דוחה", "דחייה"], "opening": "יש הבחנה אחת שחשוב לי לשים עליה רגע אור."},
    {"topic": "אמונה ומה שבידיים שלי", "words": ["אמונה", "בידיים שלי", "קב\"ה"], "opening": "יש משפט שנכתב כאן ונשאר איתי."},
]
WEEK_TARGET = (2, 3)  # guide §6: 2-3 meaningful pieces a week beat forced daily content


def _tz() -> ZoneInfo:
    return ZoneInfo(settings.timezone)


def _utc(local: datetime) -> datetime:
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _week_start(today: date) -> date:
    """Sunday, the start of the Israeli week."""
    return today - timedelta(days=(today.weekday() + 1) % 7)


def _last_touched(db: Session, words: list[str]) -> datetime | None:
    cond = or_(*[ContentItem.topic.ilike(f"%{w}%") | ContentItem.text.ilike(f"%{w}%") for w in words])
    return db.scalar(select(func.max(ContentItem.created_at)).where(cond))


def suggest_topic(db: Session, today: date) -> dict:
    """The topic she has not written about for the longest time. Never-touched topics
    come first, rotated by the day so the same one is not suggested every morning."""
    touched = [(t, _last_touched(db, t["words"])) for t in TOPICS]
    never = [t for t, when in touched if when is None]
    if never:
        pick, when = never[today.toordinal() % len(never)], None
    else:
        pick, when = min(touched, key=lambda tw: tw[1])
    days = None if when is None else (today - when.date()).days
    return {"topic": pick["topic"], "opening": pick["opening"], "days_since": days,
            "prompt": f"תכתבי הודעה לקבוצה על {pick['topic']}. אפשר לפתוח ב: \"{pick['opening']}\""}


def morning_card(db: Session, now: datetime | None = None) -> dict:
    now = now or datetime.now(_tz())
    today = now.date()
    week_from = _utc(datetime.combine(_week_start(today), time.min, tzinfo=_tz()))
    published = db.scalar(select(func.count()).select_from(ContentItem)
                          .where(ContentItem.status == "published", ContentItem.created_at >= week_from)) or 0
    low, high = WEEK_TARGET
    if published == 0:
        pace = "השבוע עוד לא עלה תוכן. אם מתאים לך, אפשר להתחיל מנושא אחד קטן."
    elif published < low:
        pace = f"השבוע עלה תוכן אחד. אם מתאים, יש מקום לעוד אחד או שניים."
    elif published <= high:
        pace = f"השבוע עלו {published} תכנים. זה בדיוק הקצב שבחרת 💛"
    else:
        pace = f"השבוע עלו {published} תכנים. אפשר גם לנוח."

    drafts = db.scalars(select(ContentItem).where(ContentItem.status == "draft")
                        .order_by(ContentItem.created_at.desc()).limit(3)).all()
    draft_count = db.scalar(select(func.count()).select_from(ContentItem).where(ContentItem.status == "draft")) or 0

    y_start = _utc(datetime.combine(today - timedelta(days=1), time.min, tzinfo=_tz()))
    y_end = _utc(datetime.combine(today, time.min, tzinfo=_tz()))
    cost = float(db.scalar(select(func.coalesce(func.sum(Run.cost_usd), 0.0))
                           .where(Run.created_at >= y_start, Run.created_at < y_end)) or 0.0)

    return {
        "date": today.isoformat(),
        "greeting": "בוקר טוב 🌱",
        "published_this_week": published,
        "week_target": f"{low}-{high}",
        "pace": pace,
        "suggestion": suggest_topic(db, today),
        "drafts_waiting": draft_count,
        "drafts": [{"id": d.id, "topic": d.topic} for d in drafts],
        "cost_yesterday_usd": round(cost, 2),
        "daily_cap_usd": settings.daily_cap_usd,
    }


def card_text(card: dict) -> str:
    s = card["suggestion"]
    since = "עוד לא כתבת עליו" if s["days_since"] is None else f"לא כתבת עליו {s['days_since']} ימים"
    lines = [f"{card['greeting']} · {card['date']}",
             card["pace"],
             f"נושא שאפשר לחזור אליו: {s['topic']} ({since}).",
             f"פתיחה אפשרית: {s['opening']}"]
    if card["drafts_waiting"]:
        lines.append(f"טיוטות שמחכות: {card['drafts_waiting']} (" + ", ".join(d["topic"] for d in card["drafts"]) + ")")
    lines.append(f"עלות אתמול: ${card['cost_yesterday_usd']:.2f} מתוך ${card['daily_cap_usd']:.2f} ליום")
    return "\n".join(lines)


def build_digest(db: Session, now: datetime | None = None) -> str:
    return card_text(morning_card(db, now))


def send_digest(text: str) -> bool:
    """POST {"text": ...} to DIGEST_WEBHOOK_URL (Slack-compatible). Returns False when no URL is set."""
    if not settings.digest_webhook_url:
        return False
    import httpx

    r = httpx.post(settings.digest_webhook_url, json={"text": text}, timeout=15)
    r.raise_for_status()
    return True


def main() -> None:
    init_db()
    with SessionLocal() as db:
        body = build_digest(db)
    print(body)
    sent = send_digest(body)
    print(f"\n[sent to webhook: {sent}]")


if __name__ == "__main__":
    main()
