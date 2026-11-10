"""The content library: save, search by word, format, status and date, and what the model sees."""
import json
from datetime import datetime, timedelta

import pytest

from app.db import ContentItem
from app.tools import registry
from app.tools.library import mark_published, save_content, search_content


@pytest.fixture(autouse=True)
def empty_library(client, db):
    """The test database is shared; start every test here with an empty library.
    `client` starts the app, which creates the tables."""
    db.query(ContentItem).delete()
    db.commit()


def test_save_then_search_by_word_in_topic_or_text(db):
    save_content(db, text="יש הבחנה אחת על הפחד לאכזב.", topic="הפחד לאכזב", format="community")
    save_content(db, text="משהו על אשמה ועל ריצוי.", topic="אשמה", format="post", status="published")
    assert [i["topic"] for i in search_content(db, query="לאכזב")["items"]] == ["הפחד לאכזב"]
    assert [i["topic"] for i in search_content(db, query="ריצוי")["items"]] == ["אשמה"]
    assert search_content(db)["count"] == 2


def test_filters_by_format_and_status(db):
    save_content(db, text="א", topic="נושא א", format="community")
    save_content(db, text="ב", topic="נושא ב", format="post", status="published")
    assert search_content(db, format="post")["items"][0]["topic"] == "נושא ב"
    assert search_content(db, status="draft")["items"][0]["topic"] == "נושא א"


def test_filters_by_date_range(db):
    save_content(db, text="ישן", topic="ישן")
    db.query(ContentItem).filter_by(topic="ישן").update({"created_at": datetime(2026, 1, 15, 10, 0)})
    db.commit()
    save_content(db, text="חדש", topic="חדש")
    today = datetime.now().date().isoformat()
    assert [i["topic"] for i in search_content(db, date_from="2026-01-01", date_to="2026-01-31")["items"]] == ["ישן"]
    yesterday = (datetime.now().date() - timedelta(days=1)).isoformat()
    assert "חדש" in [i["topic"] for i in search_content(db, date_from=yesterday, date_to=today)["items"]]


def test_empty_text_or_topic_is_not_saved(db):
    assert "error" in save_content(db, text="  ", topic="נושא")
    assert "error" in save_content(db, text="טקסט", topic="")
    assert db.query(ContentItem).count() == 0


def test_unknown_format_and_status_fall_back(db):
    out = save_content(db, text="טקסט", topic="נושא", format="tweet", status="maybe")
    assert out["format"] == "other" and out["status"] == "draft"


def test_long_text_is_previewed_not_returned_whole(db):
    save_content(db, text="מילה " * 200, topic="ארוך")
    preview = search_content(db)["items"][0]["preview"]
    assert len(preview) <= 201 and preview.endswith("…")


def test_mark_published_updates_the_same_row(db):
    item_id = save_content(db, text="טקסט", topic="נושא")["id"]
    assert mark_published(db, id=item_id)["updated"] is True
    assert mark_published(db, id=item_id)["already_published"] is True
    assert db.query(ContentItem).count() == 1
    assert search_content(db, status="published")["items"][0]["id"] == item_id


def test_mark_published_unknown_id_is_an_error(db):
    assert "error" in mark_published(db, id=9999)


def test_model_sees_content_tools_not_bakery_tools(db):
    assert {"check_text", "save_content", "mark_published", "search_content"} == registry.TOOL_NAMES
    out = json.loads(registry.execute("save_content", {"text": "טקסט", "topic": "נושא"}, db, user_id=None))
    assert out["saved"] is True
    found = json.loads(registry.execute("search_content", {"query": "נושא"}, db))
    assert found["count"] == 1
