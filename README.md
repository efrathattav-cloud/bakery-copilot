# בוחרות באומץ · Content Copilot

A content copilot for Efrat-Yaara Hattav's women's community **"בוחרות באומץ"** (choosing with courage: boundaries, people-pleasing, fear of disappointing). It drafts community messages, posts and replies **in her brand voice**, checks texts against her voice rules, suggests replies to comments from a screenshot, and keeps a library of what she wrote.

Built from [MaceTenth/bakery-copilot](https://github.com/MaceTenth/bakery-copilot) (course final project, task 9). Same four layers, a chat UI, a FastAPI backend with an agent loop, Claude, and Postgres, with a new job.

**Live on Railway:** _link added after the first deploy_

## What it does

| Ask | What happens |
|---|---|
| "תכתבי הודעה לקבוצה על אשמה" | A draft in her voice. Before showing it, the bot runs `check_text` and fixes what it finds. |
| "תבדקי לי את הטקסט הזה…" | Feedback: the mechanical findings from `check_text`, plus tone and structure notes. |
| 📎 a screenshot of a comment | Names the comment type, suggests one short reply, never mentions the participant's name. |
| "על מה כתבתי החודש?" | Searches the content library. |
| "תשמור את זה" / "פרסמתי" | Saves to the library, or marks an existing draft as published (no duplicates). |
| Open the app | A morning card: this week's pace against her 2 to 3 target, a core topic she has not touched for a while, drafts waiting. |

## How it is built

- **Prompt:** [app/prompts/system.md](app/prompts/system.md), written from her brand-voice guide: voice and tone, structure by format, how to reply to participants, banned phrases, never invent a story, privacy.
- **Tools** ([app/tools/](app/tools/)):
  - `check_text`: the mechanical half of her pre-publish checklist, in plain code with no model: long dashes, banned phrases and openings, exclamation marks, questions, emoji outside her list, length by format.
  - `save_content`, `search_content`, `mark_published`: the content library (`content_items` table).
- **Morning card:** [app/digest.py](app/digest.py), built in code from the library (no model call, so it costs nothing). Shown at `GET /api/morning`.
- **UI:** [static/](static/), Hebrew and right-to-left, in the logo's colours.
- Limits from the original project stay: shared password, 30 messages per hour, a daily spend cap (`DAILY_CAP_USD`).

## Run it locally

```bash
cp .env.example .env         # set APP_PASSWORD, APP_SECRET, ANTHROPIC_API_KEY
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

On Windows (PowerShell): `Copy-Item .env.example .env`, `py -m venv .venv`, `.venv\Scripts\Activate.ps1`, then the same two lines. Open http://localhost:8000, type a name and the password.

## Tests and evals

```bash
pytest -q                    # 49 tests, model mocked, seconds, no key needed
python -m evals.run          # 9 cases against the real model, about $0.20
```

The evals ([evals/cases.yaml](evals/cases.yaml)) check behaviour, not wording: the voice rules hold, no invented personal story, `check_text` runs on drafts and feedback, the library is searched before answering about past texts, nothing is saved unless asked, "I published it" updates instead of duplicating, short replies stay short, out-of-scope questions are declined. Last run: **9/9**.

## Deploy on Railway

1. New project → **Deploy from GitHub repo** → this repo, branch `main`. Railpack builds from `requirements.txt` and `.python-version`; no Dockerfile.
2. **+ New → Database → PostgreSQL.**
3. Variables on the web service: `APP_ENV=production`, `APP_PASSWORD`, `APP_SECRET` (32+ random characters), `ANTHROPIC_API_KEY`, `DATABASE_URL=${{Postgres.DATABASE_URL}}`, `TIMEZONE=Asia/Jerusalem`, optionally `MODEL`, `DAILY_CAP_USD`.
4. Settings → Deploy → start command `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, health check path `/health`.
5. Settings → Networking → **Generate Domain**. Open it, sign in, ask for a draft.

The original course guide, with CLI commands and troubleshooting, is in [docs/deploy-railway.md](docs/deploy-railway.md). Deploy on push to `main` is on by default.

## Cost

Railway: about $5 a month (one web service and a small Postgres). Claude: a draft costs about 3 to 5 cents with Opus 5.5; `DAILY_CAP_USD` (default $3) is the brake.

## Layout

```
app/            main.py (API), agent.py (loop), tools/, db.py, auth.py, limits.py, costs.py, digest.py
app/prompts/    system.md: the copilot's voice and rules
static/         the chat UI (plain HTML, CSS, JS), logo
tests/          pytest, model mocked
evals/          cases.yaml, run.py, history.csv
```
