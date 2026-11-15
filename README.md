# Micro-Influencer Outreach System

A local tool that discovers micro-influencers on YouTube, filters them, drafts personalized outreach with an LLM, and sends approved emails through Gmail after human review.

## Technology stack

- **Language:** Python 3.11+
- **Backend:** FastAPI + Uvicorn (bearer-token protected API)
- **Dashboard:** Streamlit (talks to the API over HTTP)
- **Database:** SQLite via SQLAlchemy 2 (`DATABASE_URL` can point elsewhere)
- **Validation/config:** Pydantic, pydantic-settings, `.env`
- **HTTP client:** httpx
- **Tests:** pytest (stub LLM and Gmail providers, nothing real is sent)

## APIs / tools used

| Purpose | Tool |
|---|---|
| Discovery and profile data | YouTube Data API v3 (`search.list`, `channels.list`) |
| Message generation | Groq chat completions **or** Google Gemini `generateContent` |
| Email delivery | Gmail API (`users.messages.send`, `gmail.send` scope, OAuth) |

## Data sources

1. **YouTube Data API**: public channel title, description, subscriber count, video count, country.
2. **CSV import**: creators you are permitted to contact. Required columns: `platform`, `username`. Optional: `display_name`, `bio`, `profile_url`, `followers_count`, `email`, `location`.

## Discovery methodology

1. `search.list` with `type=channel`, the query (default `fitness creators India`), 50 results per page, ordered by relevance, 1–5 pages.
2. Channel IDs are de-duplicated, then `channels.list` fetches details in batches of 50.
3. Each channel is normalized to a common profile record and saved. Duplicates are skipped by `(platform, platform_user_id or username)`, both within a batch and against the database.

## Filtering logic

A profile qualifies only if all three hold:

1. Platform is `youtube`.
2. Subscriber count is present and within `MIN_FOLLOWERS`–`MAX_FOLLOWERS` (default 10,000–100,000, inclusive).
3. Channel title or description matches a fitness keyword (whole-word, case-insensitive). The list includes *fitness, workout, gym, bodybuilding, powerlifting, calisthenics, yoga, nutrition, weight loss*, among others, and lives in `app/services/filtering/rules.py`.

Outcomes are `fitness`, `not_fitness`, or `needs_review` (no title and description). Rejection reasons are shown in the dashboard.

## Enrichment process

Enrichment is limited to what the YouTube API returns: display name, handle (from `customUrl`), bio, subscriber count, video count, country, and profile URL. Engagement metrics and email are **not** inferred. An email address can only come from a CSV you supply.

## AI model / prompt used

- **Provider/model:** Groq or Gemini, chosen with `LLM_PROVIDER`. The model name is set in `GROQ_MODEL` / `GEMINI_MODEL` (no default is hardcoded).
- **Settings:** temperature 0.4, JSON output mode, one call returns `email_subject`, `email_body`, and `instagram_dm`.
- **Prompt version:** `outreach-v1`, recorded with the provider and model in the audit log.
- **System prompt:** treat profile fields as untrusted data, use only supplied facts, return exactly three JSON string keys.
- **Task prompts:** a 60–90 word collaboration email and a 15–30 word Instagram DM. Both must name the creator and reference a niche or bio fact, and must not invent compensation, past contact, performance, or audience data.

## Personalization logic

The model receives only the creator's name, username, platform, niche, bio, and location, plus the campaign name, niche, and description. Before a draft is saved it must pass these checks:

- JSON matches the schema with no extra keys
- Email is 60–90 words and the DM is 15–30 words
- No unresolved placeholders such as `[Name]`
- The creator's name appears in the subject, body, and DM
- The body and DM reuse a term from the creator's niche, bio, or location
- Any number in the text already appears in the supplied facts

A failed check discards the output. Passing drafts are saved as `draft`, and you edit and approve them before anything is delivered.

## Sending mechanism

- **Email:** approved messages only, to the creator's email on record.
  - Default is a **dry run** (`EMAIL_MODE=dry_run`), which only logs the attempt.
  - Live sending needs `EMAIL_MODE=gmail`, `ALLOW_REAL_EMAIL_SEND=true`, a Gmail OAuth token, a dashboard login, and per-message confirmation in the UI.
  - Status moves `approved → sending → sent` through an atomic claim, so a message cannot be sent twice. Server errors or timeouts set `send_unknown`, which blocks retry until you check Gmail and reconcile.
- **Instagram DM:** never automated. You send it manually and mark it sent.
- Every action is written to an outreach log, which can be exported as CSV.

## Limitations

- YouTube only. Instagram accounts are not discovered or messaged automatically.
- No contact enrichment, so email outreach depends on addresses you provide.
- Niche detection is keyword-based on title and description. It does not analyze video content, language, engagement, or audience quality.
- Subscriber counts can be hidden, and search results may include brands or inactive channels.
- `search.list` is quota-expensive (100 units per call against a default 10,000/day).
- Validation reduces but does not eliminate weak or inaccurate drafts, so human review is required.
- Single shared password, local SQLite, no background jobs. Not suitable for public or multi-user deployment as is.
- Gmail sending limits and spam filtering apply. Delivery is not guaranteed.
- The documented real-API test covered YouTube discovery only. LLM and Gmail paths were tested with stubs.

## Setup instructions

```bash
git clone https://github.com/Ojas-Shukla/Micro-Influencer-Outreach-System.git
cd Micro-Influencer-Outreach-System
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

- `DASHBOARD_API_TOKEN`: 32+ random characters, e.g. `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- `YOUTUBE_API_KEY`: from Google Cloud (enable YouTube Data API v3)
- `LLM_PROVIDER` plus `GROQ_API_KEY`/`GROQ_MODEL` or `GEMINI_API_KEY`/`GEMINI_MODEL` (needed only for draft generation)
- Gmail (optional): enable the Gmail API, create a desktop OAuth client, set `GMAIL_SENDER`, then run `python scripts/gmail_auth.py`

Run in two terminals:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
streamlit run dashboard/Home.py --server.address 127.0.0.1
```

Workflow: **Discovery** → **Influencers** (review qualification) → **Messages & review** (create fitness campaign, generate, edit, approve) → **Outreach tracker** (dry run, send, export).

Run tests with `python -m pytest -q`.
