# FlowMind — AI-powered Knowledge & Task Management

Teams lose context when work changes hands. **FlowMind** captures what was discussed and decided, hands that context to the right people, and keeps chasing open items until they are closed with a recorded outcome.

Stack: **Python 3.12 · FastAPI · SQLAlchemy · SQLite (local) / PostgreSQL (deployed) · vanilla JS + CSS (no build step, no CDN dependencies) · Gemini via REST**.

## Run locally (VS Code)

```bash
python -m venv venv
venv\Scripts\activate            # Windows   (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env           # Mac/Linux: cp .env.example .env   then add AI_API_KEY
uvicorn app.main:app --reload
```
Open http://localhost:8000 (UI) and http://localhost:8000/docs (interactive API). The database is created and seeded automatically on first start. Tests: `pip install pytest && pytest`.

## What it does (mapped to the brief)

| Requirement | Where |
|---|---|
| Create & persist meetings / work transfers (agenda, participants, notes, decisions, action items) | Meetings → New; `type` is `meeting` or `handover` |
| Add rough notes when someone missed a meeting | Paste notes or upload `.txt`, `.md`, text-based `.pdf`, or a `.zip` bundle in the meeting Notes section |
| Lifecycle + track every item (owner, due date, status) until closed | Meeting status `planned → held → closed`; item status `open / in_progress / done / dropped`; board with drag-and-drop |
| Carry open items forward, keep history | **Carry forward** copies items to a new or existing meeting in one transaction, keeps `original_meeting_id` + `parent_item_id`, marks the source `carried`, and writes a history event on both |
| AI turns raw info into a structured recap | Notes → **Generate recap** → editable review sheet → save |
| Catch-up brief for someone who missed it / is taking over | **Catch-up brief**, personalised per person (knows if they missed the meeting) |
| Knowledge base + retrieval-augmented answers | `/knowledge`; ask questions across indexed document passages and see the supporting sources; closed meetings are auto-archived |
| Record the outcome of each item | Closing (`done`/`dropped`) **requires** an outcome; shown on the item and kept in history |
| Validation & error handling | Pydantic on every input (lengths, enums, emails, due date not in the past); uniform JSON errors with `request_id`; friendly UI states |

## AI configuration

- **Provider:** Google Gemini, called through plain REST with `httpx` (no SDK). Set `AI_API_KEY`, `AI_MODEL` (`gemini-3.5-flash-lite`), `AI_FALLBACK_MODEL` (`gemini-3.6-flash`), `AI_EMBEDDING_MODEL` (`gemini-embedding-001`) and `AI_TIMEOUT_SECONDS` in `.env`.
- **Four AI tasks**, all in `app/ai_service.py` / `app/kb_service.py`: recap extraction, catch-up brief, KB link re-ranking, readiness advice (+ reminder drafting).
- **Data flow:** UI → FastAPI → semantic search retrieves matching passages from the local SQL vector index → Gemini answers from those passages with source references → Pydantic validation. Recaps remain an editable preview; they are saved only after user confirmation.
- **Reliability pipeline:** timeout → one retry → fallback model (with one retry) → validated output. If everything fails (or no key is set), a deterministic rule-based fallback is returned with a visible "Rule-based result" notice. No AI failure ever produces a 500.
- **Grounding:** prompts include only stored facts; the model is told never to invent owners or dates and to resolve relative dates against today's date.
- **RAG:** documents are split into overlapping passages, embedded with Gemini Embedding, and stored as vectors in the SQL database. Queries are embedded and ranked by cosine similarity; the top passages ground answers and item-document links. If embedding or generation is unavailable, the app falls back to TF-IDF retrieval and a clearly marked rule-based result.
- **Meeting note uploads:** multiple text/Markdown/PDF files or a ZIP of those formats are safely extracted in memory and appended to the meeting notes. Uploads are capped at 5 MB, eight files, and 50,000 combined note characters; no uploaded files are saved to disk.
- **Privacy:** the included dataset is fictional. With Gemini configured, document passages and questions sent to the embedding/generation APIs leave the local app. Do not enter real company-confidential data unless the company approves that provider and data flow.

## Special feature: Context Health

Open any meeting or handover and click **Check context health**. You get a 0–100 score and an animated ring, a per-check breakdown, and an AI-written "fix first" list.

The score uses deterministic checks for owners (20), due dates (10), overdue items (10), recorded decisions (10), summary (10), knowledge links (5), agenda (5), unresolved blockers (10), repeated carry-forward (10), and decision-to-action keyword overlap (10). The last check is a simple, transparent title-keyword heuristic and can miss semantically related work. AI reads failed checks and suggests fixes; it does not calculate the score.

Why it adds value: the problem statement is about context lost at handoffs. Instead of only *recording* context, FlowMind tells the person leaving exactly what is missing **before** they leave.

Supporting features: one-click **Hand over** (bulk-reassign everything a person owns when they go on leave), priority and blocker tracking on tasks, duplicate-safe carry-forward, CSV exports for meetings and tasks, AI-drafted **reminder nudges**, and closed meetings automatically becoming searchable knowledge.

## Data source

All data is my own, in `app/seed.py`: a fictional payments team (Northwind) with 4 meetings (a closed retro, sprint planning, a handover for a colleague on leave, an upcoming weekly sync), 13 action items in every state (including an overdue item, an unowned item, a dropped item with an outcome, and a carry-forward chain from the retro into sprint planning), RSVP/attendance mix, and 7 realistic KB documents (release process, on-call guide, billing runbook, API versioning policy, postmortem template, onboarding, load testing). Dates are relative to today so the demo never goes stale. Seeding runs only when the DB is empty.

## Login and accounts

The first visitor sees **Create your admin account**; this creates the initial workspace admin. Admins can add member/admin accounts and disable accounts from the account panel. All `/api` routes except health and the auth bootstrap/login/logout endpoints require a valid signed session cookie. Passwords use salted PBKDF2-SHA256 hashes; sessions use HttpOnly, SameSite=Strict cookies and are revoked when an account is disabled or its password changes. Members can use the shared workspace; only admins can manage accounts.

Set `AUTH_SECRET` in `.env` to a long random value so sessions survive app restarts. Set `AUTH_COOKIE_SECURE=true` when serving over HTTPS. The local setup uses a generated secret in `.env`; do not commit that file. This is a single-workspace role model, not per-record or multi-tenant authorization.

## Logging

- `app/logger.py`: stdlib `logging`, one JSON object per line, to `logs/app.log` (rotating, 2 MB × 5) **and** the console. Levels via `LOG_LEVEL`.
- A middleware assigns a **correlation ID** per request (or honours an incoming `X-Request-ID`), stores it in a `ContextVar`, stamps it on every log line, and returns it in the `X-Request-ID` response header and in every error body.
- Key events: `meeting_created`, `meeting_notes_uploaded`, `action_item_created`, `action_item_reassigned`, `bulk_reassigned`, `action_item_closed`, `items_carried_forward`, `recap_applied`, `kb_linked`, `kb_rag_answered`, `readiness_scored`, `request` (method, path, status, duration).
- AI calls: `ai_call` per attempt with `task`, `model`, `attempt`, `latency_ms`, `outcome`, `error`; `ai_fallback_used` when degraded. Prompts and notes are **never** logged (only their length).
- No secrets: API keys are redacted by pattern and by exact value before any handler writes; httpx URL logging is silenced because Gemini URLs can contain keys. Covered by a test.

## Approach & decisions

- **Relational DB (SQL):** meetings, items, history, knowledge documents, chunks and their vectors are persisted together; carry-forward uses transactional all-or-nothing writes.
- **One-variable DB switch:** `DATABASE_URL` selects SQLite locally or Postgres in production, because free hosts wipe local disks.
- **No front-end framework:** vanilla JS keeps the app dependency-free and offline-safe; the UI is hash-routed with event delegation.
- **Human in the loop:** AI proposes, the user confirms.
- **History as a first-class table** (`action_item_history`) so every reassignment, date change, status change, carry-forward and outcome is traceable.

## Deploy (Render + Neon Postgres)

1. Push to GitHub. 2. Create a free Postgres on Neon and copy its connection string. 3. On Render: **New → Blueprint** (uses `render.yaml`) or a Web Service with build `pip install -r requirements.txt` and start `uvicorn app.main:app --host 0.0.0.0 --port $PORT`. 4. In the dashboard set `DATABASE_URL` and `AI_API_KEY`. The app creates tables and seeds on first boot. Check `/api/health`.

## Assumptions

Single team, no authentication (people are plain names, not user accounts); one timezone; "AI provider" is Gemini but isolated behind `call_json()` so another provider is a small change; item owners are free text so that people outside the meeting can own items.

## Known limitations

- No auth / permissions; anyone with the URL can edit.
- No Alembic migrations (`create_all` on startup); schema changes need a manual migration.
- If Gemini embeddings are unavailable, the fallback TF-IDF search is lexical, so it can miss synonym-based matches.
- Rule-based recap fallback understands simple "Name will …" patterns only.
- Note uploads accept text-based PDFs; scanned/image-only PDFs are not OCR-processed. ZIP bundles may contain up to eight `.txt`, `.md`, or `.pdf` notes.
- Free hosting sleeps when idle (first request can take ~30–60 s) and free AI tiers are rate-limited and may use prompts to improve products — don't paste confidential data.
- Reminders are drafted, not sent (no email/Slack integration).
- Drag-and-drop on the board is mouse-only; on touch devices use the item sheet to change status.
