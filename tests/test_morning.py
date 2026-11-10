"""The morning card: weekly pace, the topic left longest untouched, drafts waiting."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.db import ContentItem
from app.digest import TOPICS, card_text, morning_card, suggest_topic
from app.tools.library import save_content

TZ = ZoneInfo("Asia/Jerusalem")
TUESDAY = datetime(2026, 11, 10, 8, 0, tzinfo=TZ)  # week started Sunday 8.11


@pytest.fixture(autouse=True)
def empty_library(client, db):
    db.query(ContentItem).delete()
    db.commit()


def _age(db, topic, when):
    db.query(ContentItem).filter_by(topic=topic).update({"created_at": when})
    db.commit()


def test_empty_library_suggests_an_untouched_topic(db):
    card = morning_card(db, TUESDAY)
    assert card["published_this_week"] == 0
    assert "עוד לא עלה תוכן" in card["pace"]
    assert card["suggestion"]["days_since"] is None
    assert card["suggestion"]["topic"] in {t["topic"] for t in TOPICS}


def test_a_topic_written_about_is_not_suggested_while_others_are_untouched(db):
    for t in TOPICS[1:]:
        save_content(db, text=f"טקסט על {t['words'][0]}", topic=t["topic"])
    assert suggest_topic(db, TUESDAY.date())["topic"] == TOPICS[0]["topic"]


def test_when_all_are_touched_the_oldest_is_suggested(db):
    for i, t in enumerate(TOPICS):
        save_content(db, text=f"טקסט על {t['words'][0]}", topic=t["topic"])
        _age(db, t["topic"], datetime(2026, 11, 1) + timedelta(days=i))
    s = suggest_topic(db, TUESDAY.date())
    assert s["topic"] == TOPICS[0]["topic"] and s["days_since"] == 9


def test_pace_counts_only_this_weeks_published_texts(db):
    save_content(db, text="א", topic="השבוע", status="published")
    save_content(db, text="ב", topic="שבוע שעבר", status="published")
    _age(db, "השבוע", datetime(2026, 11, 9, 9, 0))
    _age(db, "שבוע שעבר", datetime(2026, 11, 5, 9, 0))
    card = morning_card(db, TUESDAY)
    assert card["published_this_week"] == 1 and "תוכן אחד" in card["pace"]


def test_drafts_waiting_are_listed(db):
    save_content(db, text="טיוטה", topic="טיוטה ראשונה")
    card = morning_card(db, TUESDAY)
    assert card["drafts_waiting"] == 1 and card["drafts"][0]["topic"] == "טיוטה ראשונה"
    assert "טיוטות שמחכות: 1" in card_text(card)


def test_card_text_has_no_long_dash(db):
    assert "—" not in card_text(morning_card(db, TUESDAY))


def test_morning_endpoint_needs_login(client, logged_in):
    assert client.get("/api/morning").json()["greeting"].startswith("בוקר טוב")
    client.cookies.clear()
    assert client.get("/api/morning").status_code == 401
