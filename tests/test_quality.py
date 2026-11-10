"""check_text catches each mechanical brand-voice rule, and a clean text passes."""
import json

from app.tools import registry
from app.tools.quality import check_text

CLEAN = (
    "יש הבחנה אחת שחשוב לי לשים עליה רגע אור.\n"
    "הרבה פעמים ה\"לא\" כבר ברור לנו. מה שעוצר הוא התמונה של מי שמולנו.\n"
    "מה יותר קשה לך, להגיד את זה או להתמודד עם התגובה אחר כך? 🌱"
)


def rules(text, fmt="community"):
    return {i["rule"] for i in check_text(text, fmt)["issues"]}


def test_clean_text_passes():
    result = check_text(CLEAN, "community")
    assert result["ok"] is True and result["issues"] == []


def test_long_dash_is_caught():
    assert "long_dash" in rules("אני רוצה להגיד לא — אבל מפחדת.")


def test_banned_phrase_is_caught():
    assert "banned_phrase" in rules("הגיע הזמן לצאת מאזור הנוחות.")
    assert "banned_phrase" in rules("זה הכל בראש.")


def test_banned_opening_is_caught():
    assert "banned_opening" in rules("נשים רבות מתמודדות עם ריצוי.")


def test_exclamations_are_caught():
    assert "exclamations" in rules("זה הזמן!!!")
    assert "exclamations" not in rules("איזה יופי!")


def test_more_than_one_question_in_a_community_message():
    assert "questions" in rules("מה את מרגישה? ומה את רוצה?", "community")
    assert "questions" not in rules("מה את מרגישה? ומה את רוצה?", "marketing")


def test_emoji_outside_the_list_is_caught_but_allowed_ones_pass():
    assert "emoji" in rules("כל הכבוד 🔥")
    assert "emoji" not in rules("תודה ששיתפת ❤️ 🙏🏻 💛")


def test_length_depends_on_format():
    long_reply = " ".join(["מילה"] * 50)
    assert "length" in rules(long_reply, "reply")
    assert "length" not in rules(long_reply, "community")


def test_registry_runs_check_text():
    out = json.loads(registry.execute("check_text", {"text": "אין תירוצים!!!", "format": "post"}, db=None))
    assert out["ok"] is False
    assert {"banned_phrase", "exclamations"} <= {i["rule"] for i in out["issues"]}
    assert "check_text" in registry.TOOL_NAMES
