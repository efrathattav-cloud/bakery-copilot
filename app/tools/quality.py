"""check_text: the mechanical part of the brand-voice checklist (guide §15, §17, §19).

Plain code, no model: it catches what a language model can miss in a long draft
(a long dash, a banned phrase, too many '!'). The judgement calls ("does this
sound like her?") stay with the model.
"""
from __future__ import annotations

import re
from typing import Any

LONG_DASHES = ("—", "–")  # em dash and en dash; the guide allows only a short hyphen

BANNED_PHRASES = {
    "פשוט תעשי": "פשוט תעשי",
    "שימי את עצמך במקום הראשון": "שימי את עצמך במקום הראשון",
    "תאהבי את עצמך": "תאהבי את עצמך",
    "אזור הנוחות": "צאי מאזור הנוחות",
    "הכול בראש": "הכול בראש",
    "הכל בראש": "הכול בראש",
    "אם רק תרצי": "אם רק תרצי",
    "הגרסה הכי טובה של עצמך": "הגרסה הכי טובה של עצמך",
    "אין תירוצים": "אין תירוצים",
    "למה את מחכה": "למה את מחכה???",
}
BANNED_OPENINGS = ("נשים רבות מתמודדות",)

# The guide's emoji list, by base code point (variation selectors and skin tones ignored).
ALLOWED_EMOJI = {0x2764, 0x1F49B, 0x1F331, 0x1F3A7, 0x270D, 0x1F463, 0x1F605, 0x1F64F, 0x1F525}  # 🔥 approved 2026-11-10
_EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿]")

# Words per format: a soft ceiling, the guide's "shorter is better when nothing is lost".
MAX_WORDS = {"community": 150, "reply": 40, "recording": 60, "post": 300, "marketing": 250, "exercise": 200, "other": 300}
# Formats where more than one question usually means the message lost its focus (guide §7, §8).
ONE_QUESTION_FORMATS = {"community", "reply", "recording"}
FORMATS = sorted(MAX_WORDS)


def check_text(text: str, format: str = "other") -> dict[str, Any]:
    fmt = format if format in MAX_WORDS else "other"
    issues: list[dict[str, str]] = []

    dashes = sum(text.count(d) for d in LONG_DASHES)
    if dashes:
        issues.append({"rule": "long_dash", "detail": f"{dashes} long dash(es). Replace with a comma, period or colon."})

    found = sorted({label for phrase, label in BANNED_PHRASES.items() if phrase in text})
    if found:
        issues.append({"rule": "banned_phrase", "detail": "Avoid: " + ", ".join(found)})

    if text.strip().startswith(BANNED_OPENINGS):
        issues.append({"rule": "banned_opening", "detail": "Do not open with 'נשים רבות מתמודדות'. Open with a real moment or a sentence she says to herself."})

    exclamations = text.count("!")
    if exclamations > 1 or "!!" in text:
        issues.append({"rule": "exclamations", "detail": f"{exclamations} exclamation marks. Keep at most one."})

    questions = text.count("?")
    if fmt in ONE_QUESTION_FORMATS and questions > 1:
        issues.append({"rule": "questions", "detail": f"{questions} questions. In a {fmt} message one question is usually enough."})

    other_emoji = sorted({ch for ch in _EMOJI.findall(text)
                          if ord(ch) not in ALLOWED_EMOJI and not 0x1F3FB <= ord(ch) <= 0x1F3FF})  # skin tones
    if other_emoji:
        issues.append({"rule": "emoji", "detail": "Emoji not on the list: " + " ".join(other_emoji)})

    words = len(text.split())
    if words > MAX_WORDS[fmt]:
        issues.append({"rule": "length", "detail": f"{words} words; a {fmt} text is usually up to {MAX_WORDS[fmt]}. Can it be shorter without losing depth?"})

    return {
        "ok": not issues,
        "format": fmt,
        "issues": issues,
        "stats": {"words": words, "questions": questions, "exclamations": exclamations},
    }
