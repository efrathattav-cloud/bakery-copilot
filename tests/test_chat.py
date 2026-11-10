"""Integration tests: the API with the model replaced by a scripted fake."""
from app import agent as agent_module
from app.agent import ModelEvent, run_turn
from app.costs import Usage
from app.db import ContentItem, Conversation, Message, Run, SessionLocal, User
from tests.conftest import read_sse


def test_health_ok(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_login_required_and_wrong_password(client):
    client.cookies.clear()
    assert client.get("/api/conversations").status_code == 401
    bad = client.post("/api/login", json={"name": "Eve", "password": "nope"})
    assert bad.status_code == 401
    assert client.post("/api/login", json={"name": "E", "password": "test-pass"}).status_code in (400, 422)


def test_chat_streams_text_and_saves_once(client, db, logged_in, fake):
    fake.turns.append([
        ModelEvent(type="text", text="Challah sold best "),
        ModelEvent(type="text", text="last week: 312 units."),
        ModelEvent(type="stop", stop_reason="end_turn", usage=Usage(120, 18),
                   content=[{"type": "text", "text": "Challah sold best last week: 312 units."}]),
    ])
    r = client.post("/api/chat", json={"message": "What sold best last week?"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = read_sse(r)
    kinds = [e["type"] for e in events]
    assert kinds[0] == "meta" and kinds[-1] == "done"
    assert "".join(e["text"] for e in events if e["type"] == "text") == "Challah sold best last week: 312 units."
    conv_id = events[0]["conversation_id"]
    msgs = db.query(Message).filter_by(conversation_id=conv_id).order_by(Message.id).all()
    assert [m.role for m in msgs] == ["user", "assistant"]
    assert msgs[1].content == "Challah sold best last week: 312 units."
    run = db.query(Run).filter_by(conversation_id=conv_id).one()
    assert run.status == "ok" and run.input_tokens == 120 and run.output_tokens == 18
    assert events[-1]["cost_usd"] == 0.0  # fake model has no price table


def test_tool_loop_saves_to_the_library_and_sums_both_model_calls(client, db, logged_in, fake):
    db.query(ContentItem).delete(); db.commit()
    tool_turn = [
        ModelEvent(type="text", text="שומרת. "),
        ModelEvent(type="stop", stop_reason="tool_use", usage=Usage(300, 40), content=[
            {"type": "text", "text": "שומרת. "},
            {"type": "tool_use", "id": "tu_1", "name": "save_content",
             "input": {"text": "יש הבחנה אחת.", "topic": "בדיקת לולאה", "format": "community"}},
        ]),
    ]
    final_turn = [
        ModelEvent(type="text", text="נשמר בספרייה."),
        ModelEvent(type="stop", stop_reason="end_turn", usage=Usage(420, 30),
                   content=[{"type": "text", "text": "נשמר בספרייה."}]),
    ]
    fake.turns.extend([tool_turn, final_turn])

    events = read_sse(client.post("/api/chat", json={"message": "תשמור את זה"}))
    tools = [e for e in events if e["type"] == "tool"]
    assert [t["status"] for t in tools] == ["start", "done"] and tools[0]["name"] == "save_content"
    assert db.query(ContentItem).filter_by(topic="בדיקת לולאה").count() == 1
    run = db.query(Run).filter_by(conversation_id=events[0]["conversation_id"]).one()
    assert run.tool_calls == 1 and run.input_tokens == 720  # both model calls of the turn are summed


def test_refusal_is_reported_not_hidden(client, db, logged_in, fake):
    fake.turns.append([ModelEvent(type="stop", stop_reason="refusal", usage=Usage(50, 0), content=[])])
    events = read_sse(client.post("/api/chat", json={"message": "do something odd"}))
    assert any(e["type"] == "text" and "לא אוכל לעזור" in e["text"] for e in events)
    conv_id = events[0]["conversation_id"]
    assert db.query(Run).filter_by(conversation_id=conv_id).one().status == "refusal"


def test_dropped_connection_leaves_no_half_row(client, db, logged_in, fake):
    fake.turns.append([
        ModelEvent(type="text", text="This reply will be cut "),
        ModelEvent(type="text", text="in the middle."),
        ModelEvent(type="stop", stop_reason="end_turn", usage=Usage(10, 5), content=[{"type": "text", "text": "x"}]),
    ])
    with SessionLocal() as s:
        user = s.query(User).filter_by(name="Dana").one()
        gen = run_turn(s, user=user, conversation=None, text="cut me off", image=None, client=fake)
        meta = next(gen)
        first = next(gen)
        assert meta["type"] == "meta" and first["type"] == "text"
        gen.close()  # the browser went away
        conv_id = meta["conversation_id"]
    roles = [m.role for m in db.query(Message).filter_by(conversation_id=conv_id).all()]
    assert roles == ["user"]  # the user's message is kept, no partial assistant row
    run = db.query(Run).filter_by(conversation_id=conv_id).one()
    assert run.status == "aborted"


def test_image_message_carries_a_reference(client, db, logged_in, fake):
    import base64

    fake.turns.append([ModelEvent(type="stop", stop_reason="end_turn", usage=Usage(10, 2),
                                  content=[{"type": "text", "text": "Got the image."}])])
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    events = read_sse(client.post("/api/chat", json={"message": "", "image": {"media_type": "image/png", "data": png}}))
    assert events[-1]["type"] == "done"
    sent = fake.last_messages[-1]["content"]
    assert sent[0]["type"] == "image" and sent[0]["source"]["media_type"] == "image/png"
    assert "image reference: img_" in sent[1]["text"]
    conv_id = events[0]["conversation_id"]
    user_msg = db.query(Message).filter_by(conversation_id=conv_id, role="user").one()
    assert user_msg.has_image is True and "[image img_" in user_msg.content


def test_image_without_text_is_treated_as_a_group_comment(client, db, logged_in, fake):
    import base64

    fake.turns.append([ModelEvent(type="stop", stop_reason="end_turn", usage=Usage(10, 2),
                                  content=[{"type": "text", "text": "סוג התגובה: שיתוף אישי קצר."}])])
    png = base64.b64encode(b"\x89PNG\r\n\x1a\nfake").decode()
    events = read_sse(client.post("/api/chat", json={"message": "", "image": {"media_type": "image/png", "data": png}}))
    assert events[-1]["type"] == "done"
    sent_text = fake.last_messages[-1]["content"][1]["text"]
    assert "צילום מסך של תגובה מהקבוצה" in sent_text
    assert "invoice" not in sent_text.lower()


def test_system_prompt_keeps_the_brand_voice_rules(client, db):
    # The content copilot: the prompt must name the community, keep the core
    # voice rules, and have every placeholder filled (today's date included).
    import datetime as dt

    text = agent_module.build_system(db)[0]["text"]
    assert "בוחרות באומץ" in text
    assert "Never use the long dash" in text
    assert "Never invent" in text
    assert dt.date.today().isoformat()[:4] in text
    assert "{{" not in text


def test_startup_prints_the_schema_report(client, capsys):
    # The deploy guide checks this line in the logs.
    from fastapi.testclient import TestClient

    from app.main import app

    capsys.readouterr()
    with TestClient(app):
        pass
    assert "startup report: schema_version: 1" in capsys.readouterr().out


def test_digest_endpoint_needs_secret(client, logged_in):
    assert client.post("/internal/digest").status_code == 401
    r = client.post("/internal/digest", headers={"X-Cron-Secret": "cron-test"})
    assert r.status_code == 200
    assert r.json()["text"].startswith("בוקר טוב")
    assert r.json()["sent"] is False
