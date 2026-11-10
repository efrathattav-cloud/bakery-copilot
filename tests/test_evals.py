"""The eval runner's own plumbing, with the fake model: no network, no cost."""
from app.agent import FakeModelClient
from evals import run as evals_run


def test_case_history_reaches_the_model_as_earlier_turns(client):
    fake = FakeModelClient()
    case = {"id": "t", "input": "יש לך כרטיסי טיסה?",
            "history": [{"role": "user", "content": "תכתבי משפט פתיחה על אישור"},
                        {"role": "assistant", "content": "איפה את מרגישה שאת כבר יודעת?"}]}
    result = evals_run.run_case(case, fake)
    sent = fake.last_messages
    assert [m["role"] for m in sent] == ["user", "assistant", "user"]
    assert sent[0]["content"] == "תכתבי משפט פתיחה על אישור"
    assert "כבר יודעת" in sent[1]["content"]
    assert sent[2]["content"][-1]["text"] == "יש לך כרטיסי טיסה?"
    assert result["status"] == "ok"


def test_case_without_history_is_a_single_turn(client):
    fake = FakeModelClient()
    evals_run.run_case({"id": "t", "input": "על מה כתבתי לאחרונה?"}, fake)
    assert [m["role"] for m in fake.last_messages] == ["user"]


def test_setup_library_is_saved_before_the_turn_and_graded(client):
    fake = FakeModelClient()
    case = {"id": "t", "input": "פרסמתי",
            "setup_library": [{"text": "טקסט", "topic": "נושא", "status": "draft"}],
            "expect": {"library_count": 1, "library_statuses": ["published"]}}
    result = evals_run.run_case(case, fake)
    assert result["library"][0]["topic"] == "נושא"
    assert evals_run.grade_facts(case, result) == ["library statuses ['draft'], expected ['published']"]
