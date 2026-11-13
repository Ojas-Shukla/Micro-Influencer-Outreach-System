# Micro-Influencer Outreach System

A local fitness-creator discovery, qualification, message-review, and outreach
tracking app. The Streamlit dashboard calls the authenticated FastAPI backend;
the API and dashboard run as two local processes and share a SQLite database.

## Implemented

- Import creator records from CSV or discover public YouTube channels through
  the official YouTube Data API.
- Save and deduplicate profiles in SQLite.
- Qualify YouTube profiles against the fitness rules below and show the reasons
  for accepted, rejected, and manual-review outcomes.
- Generate a personalized collaboration email and Instagram DM for each
  qualified profile through the configured Groq or Gemini provider. Validate
  the JSON schema, message lengths, creator identity, profile grounding, and
  unsupported numeric claims before saving drafts.
- Review, edit, and approve drafts in the dashboard.
- Record email dry runs; optionally send approved email through Gmail after
  explicit configuration and operator confirmation.
- Track manual Instagram DM delivery, prevent duplicate attempts, reconcile
  stale or uncertain email attempts, and export profiles and outreach logs.
- Protect API data/workflow routes with a bearer token. Require a dashboard
  password in non-development environments and whenever live email is enabled.

The API health and root routes are public. All discovery, data, message,
delivery, log, and export routes require `DASHBOARD_API_TOKEN`.

## Fitness qualification

Fitness is the only supported niche. The settings validator rejects other
`TARGET_NICHE` values and campaign creation only accepts `fitness`.

A profile is accepted only when all of these are true:

1. Its platform is YouTube.
2. Its subscriber count is available and within the inclusive configured
   `MIN_FOLLOWERS`–`MAX_FOLLOWERS` range (defaults: 10,000–100,000).
3. Its channel title or description contains one of the configured fitness
   keywords in [app/services/filtering/rules.py](./app/services/filtering/rules.py).

Missing title and description require manual review; a non-matching profile is
rejected. The app does not discover Instagram accounts, infer engagement, or
find email addresses. CSV records can contain other platforms, but only
qualifying YouTube profiles receive generated drafts. Verify an Instagram
account and the recipient address independently before contacting anyone.

## Requirements and setup

Python 3.11 or newer is recommended.

```bash
git clone <repository-url>
cd "Micro-Influencer Outreach System"
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Set a private, random API token in `.env` (at least 32 characters). For example,
generate one locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the generated value as `DASHBOARD_API_TOKEN`. Do not paste credentials into
source control, issue trackers, or logs. Add a YouTube Data API key as
`YOUTUBE_API_KEY` to use YouTube discovery. LLM keys and Gmail OAuth are
optional; generation and live email remain unavailable until their respective
credentials are configured.

The default database is `data/micro_influencer.db`; tables are created when the
API starts. `DATABASE_URL` can point to another SQLAlchemy database URL.

## Run locally

Start the API in one terminal:

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Start the dashboard in another terminal, with the same `.env` settings:

```bash
streamlit run dashboard/Home.py --server.address 127.0.0.1
```

Open the local Streamlit URL printed by the command. The API defaults to
`http://127.0.0.1:8000`; change `API_BASE_URL` only when intentionally using a
different API address. The dashboard contacts the API over HTTP and does not
open a database connection of its own.

## Dashboard workflow

1. Import a permitted CSV or run a public-channel search in **Discovery**.
   CSV input requires `platform` and `username` columns; other recognized
   fields include `display_name`, `bio`, `profile_url`, `followers_count`,
   `email`, and `location`.
2. Review qualification outcomes in **Influencers**. Missing values are not
   guessed.
3. Create a fitness campaign in **Messages & review**. Generate drafts only
   when a Groq or Gemini provider and model are configured. Edit and approve
   each draft before delivery.
4. In **Outreach tracker**, record a dry run or manually send the Instagram DM.
   Live email is disabled by default.
5. Review the activity log and download CSV exports.

Email messages contain 60–90 words and Instagram DM drafts contain 15–30 words.
The generator validates JSON shape, placeholders, profile-specific wording,
and numeric claims. These checks reduce unsupported personalization but do not
replace human review.

## Access and delivery safety

- Keep both processes bound to `127.0.0.1` for trusted local use.
- Use a unique random `DASHBOARD_API_TOKEN`; the API fails closed when it is
  missing or shorter than 32 characters.
- Set `APP_ENV` to a non-development value for non-local use. The dashboard
  then requires `DASHBOARD_LOGIN_PASSWORD` (at least 16 characters). The same
  login is required whenever live email is enabled.
- Do not expose this shared-password prototype directly to the public
  internet. For a multi-user or public deployment, put it behind an
  organization-managed identity-aware proxy/SSO, TLS, and network restrictions.
- Real email requires both `EMAIL_MODE=gmail` and
  `ALLOW_REAL_EMAIL_SEND=true`, plus Gmail OAuth credentials. The dashboard
  also requires an explicit per-message send confirmation.
- If a send outcome is uncertain, the message is blocked from retry. Wait at
  least five minutes for a stale `sending` attempt to be marked uncertain, then
  inspect the sender mailbox. Only confirm “not sent” after checking Gmail;
  that explicit reconciliation unlocks a reviewed retry.
- Instagram messages are never sent automatically. Mark them sent only after
  manually confirming delivery.

To configure Gmail OAuth after enabling the Google Gmail API and creating a
desktop OAuth client:

```bash
python scripts/gmail_auth.py
```

Store OAuth files under `.secrets/` or another private path; never commit them.
Real email sending is not required for local discovery or dry-run testing.

## Tests

Install the requirements, then run:

```bash
python -m pytest -q
```

The suite covers qualification, provider and message validation, API-to-
database workflows, API authentication, dashboard API request mapping,
duplicate prevention, dry-run and send outcomes, and uncertain-delivery
recovery. Tests use stub providers/senders; they do not send real messages.

## Real-integration demo record

On 2026-11-13, the authenticated `/discovery/youtube` API was run once against
the official YouTube Data API using the query `fitness creators` and one search
page. It returned HTTP 200: 50 channel IDs, 50 channel details, 50 imports, and
0 duplicates. All records were written to an in-memory SQLite database and
discarded after the run. The API key was not logged or included in this
documentation. The LLM and Gmail integrations were not exercised in this demo.

## Explicitly not implemented

- Instagram discovery or automated Instagram messaging.
- Email/contact enrichment or private audience analytics.
- Authentication for individual users, roles, or a full multi-tenant system.
- Production deployment, hosted database migrations, or background job
  processing.
- Guaranteed delivery, automated retry for uncertain sends, or proof that a
  public contact address is current.
