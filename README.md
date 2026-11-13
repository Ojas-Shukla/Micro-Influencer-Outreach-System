# Automated Micro-Influencer Outreach System

> **EDXSO AI Engineer Intern – Assignment 1**  
> A modular, AI-assisted pipeline to discover micro-influencers, evaluate brand fit, enrich public profiles, generate personalized outreach, and track email/DM workflows.

---

## 1. Project overview

Marketing teams often spend a significant amount of time finding creators, checking whether their audience fits a campaign, collecting contact details, writing individual messages, and tracking who has already been contacted.

This project turns that process into a repeatable workflow:

```text
Data sources
    |
    v
Influencer discovery (target: 50+ profiles)
    |
    v
Normalization + validation
    |
    v
Filtering and classification
    |
    v
Profile enrichment
    |
    v
AI personalization (email + Instagram DM)
    |
    v
Human review / approval
    |
    +--------------------------+
    |                          |
    v                          v
Email send or dry-run      DM copy/manual workflow
    |                          |
    +-------------+------------+
                  |
                  v
          Outreach tracker
```

### Example use case

A skincare brand wants to find creators in the beauty niche with 5,000–100,000 followers. The application discovers candidate creators, evaluates their available profile metrics and content themes, records why each creator passed or failed, and generates a tailored collaboration email and short Instagram DM for qualified creators.

### What the system does

1. Discovers creators from configured, permitted data sources.
2. Normalizes different source records into one common influencer schema.
3. Filters creators using configurable rules (initially, one complete niche such as Beauty & Skincare).
4. Enriches shortlisted records using publicly available information.
5. Marks missing contact information as `Not Found`; it never guesses an email address.
6. Generates a 60–90 word email pitch and a 15–30 word Instagram DM.
7. Provides a review step before sending.
8. Sends emails only when explicitly enabled, or runs in dry-run mode.
9. Stores delivery status and prevents duplicate outreach.
10. Exports the influencer dataset and outreach log to CSV.

### What the system does not promise

- It does not guarantee that every social platform can be searched through an official public API.
- It does not bypass logins, CAPTCHAs, rate limits, robots rules, or platform access controls.
- It does not infer private audience demographics or invent engagement metrics.
- It does not automatically send Instagram DMs through unofficial methods.
- It does not guarantee that an email address found on a public page is current or deliverable.

---

## 2. Recommended technology stack

The initial version is designed to run locally without paid infrastructure.

| Layer | Recommended choice | Purpose |
|---|---|---|
| Language | Python 3.11+ | Main application language |
| API/backend | FastAPI | REST endpoints and workflow orchestration |
| Dashboard | Streamlit | Local UI for discovery, review, messages and tracking |
| Database | SQLite + SQLAlchemy | Local persistent storage |
| Data validation | Pydantic | Validate source records and API payloads |
| Data processing | pandas | Cleaning, filtering and CSV export |
| HTTP | httpx | External API requests |
| LLM | Groq **or** Google Gemini | Personalized outreach generation |
| Email | Gmail API (OAuth) | Optional real email delivery |
| Testing | pytest | Unit and integration tests |
| Configuration | python-dotenv / pydantic-settings | Environment variables and secrets |
| Logging | Python logging | Diagnostics and audit trail |

**Why this stack?** FastAPI separates business logic from the user interface. Streamlit makes it easy to demonstrate the workflow. SQLite avoids hosting costs for a 50–500 creator prototype. SQLAlchemy makes a future move to PostgreSQL easier.

For a small assignment, run the FastAPI backend and Streamlit dashboard on the same laptop. Do not add Docker, Redis, Celery, Kubernetes, or a paid cloud database until there is a demonstrated need.

---

## 3. Free-tier AI provider: Groq or Gemini

Anthropic is not required. Keep the LLM integration behind one interface so the rest of the project does not depend on a particular provider.

### Option A — Groq

- Create an API key from the Groq Console.
- Install the official Python SDK: `pip install groq`.
- Configure `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and a model currently available to your account.
- Groq uses a chat-completions interface.
- Free-plan limits are model- and account-dependent. Handle HTTP 429 responses and check the live limits in the console.

### Option B — Google Gemini

- Create an API key in Google AI Studio.
- Install the Google Gen AI SDK: `pip install google-genai`.
- Configure `LLM_PROVIDER=gemini`, `GEMINI_API_KEY`, and a model currently available on your account.
- The Gemini API has a free tier for selected models, subject to usage limits. Check the current model-specific limits before running a batch.

### Which should you choose?

Start with **Groq** for a simple text-generation prototype, or choose **Gemini** if you already have an AI Studio key. Either is suitable for generating short outreach messages. The application should support both through the same provider interface.

Do not hard-code a model name in business logic. Put it in `.env`; model availability and free-tier limits can change.

### Example `.env.example`

```dotenv
APP_ENV=development
DATABASE_URL=sqlite:///./data/influencer_outreach.db

# Choose: groq or gemini
LLM_PROVIDER=groq

# Groq
GROQ_API_KEY=
GROQ_MODEL=

# Gemini
GEMINI_API_KEY=
GEMINI_MODEL=

# Discovery sources: enable only providers you have permission to use
YOUTUBE_API_KEY=

# Email is disabled by default
EMAIL_MODE=dry_run
GMAIL_SENDER=

# Set true only after configuring OAuth and reviewing the messages
ALLOW_REAL_EMAIL_SEND=false

# Initial campaign defaults
TARGET_NICHE=beauty
MIN_FOLLOWERS=5000
MAX_FOLLOWERS=100000
MIN_ENGAGEMENT_RATE=2.0
```

Never commit `.env`, API keys, OAuth tokens, client secrets, or database files containing personal contact information. Commit only `.env.example`.

---

## 4. Industry-style folder structure

Keep source adapters, business rules, LLM code, persistence, API routes, and UI separate. This avoids putting the whole project in one large Python file.

```text
micro-influencer-outreach/
│
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application entry point
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   └── routes/
│   │       ├── discovery.py        # Start discovery / list discovered creators
│   │       ├── influencers.py      # Read, filter and update creator records
│   │       ├── campaigns.py        # Campaign configuration and execution
│   │       ├── messages.py         # Generate and review messages
│   │       └── outreach.py         # Dry-run, send and delivery status
│   │
│   ├── core/
│   │   ├── config.py               # Settings loaded from environment
│   │   ├── logging.py              # Logging configuration
│   │   └── exceptions.py           # Application-specific exceptions
│   │
│   ├── db/
│   │   ├── base.py                 # SQLAlchemy base
│   │   ├── session.py              # Database session management
│   │   └── models/
│   │       ├── influencer.py
│   │       ├── campaign.py
│   │       ├── message.py
│   │       └── outreach_log.py
│   │
│   ├── schemas/
│   │   ├── influencer.py           # Pydantic request/response schemas
│   │   ├── campaign.py
│   │   ├── message.py
│   │   └── outreach.py
│   │
│   ├── repositories/
│   │   ├── influencer_repository.py
│   │   ├── campaign_repository.py
│   │   └── outreach_repository.py
│   │
│   ├── services/
│   │   ├── discovery/
│   │   │   ├── base.py             # Common discovery-provider interface
│   │   │   ├── youtube.py          # YouTube Data API adapter
│   │   │   └── import_csv.py       # Permitted CSV/manual source adapter
│   │   │
│   │   ├── filtering/
│   │   │   ├── rules.py            # Configurable eligibility rules
│   │   │   └── classifier.py       # Pass/fail and reason generation
│   │   │
│   │   ├── enrichment/
│   │   │   ├── profile_enricher.py # Public profile / website enrichment
│   │   │   └── email_finder.py     # Extract only explicitly published emails
│   │   │
│   │   ├── llm/
│   │   │   ├── base.py             # LLM provider interface
│   │   │   ├── groq_provider.py
│   │   │   ├── gemini_provider.py
│   │   │   ├── prompt_templates.py
│   │   │   └── message_generator.py
│   │   │
│   │   └── outreach/
│   │       ├── email_sender.py     # Gmail API integration
│   │       ├── dm_workflow.py      # Manual/copy-ready DM workflow
│   │       ├── duplicate_guard.py  # Idempotency / duplicate prevention
│   │       └── tracker.py          # Status updates and audit log
│   │
│   └── utils/
│       ├── text.py
│       ├── metrics.py
│       └── validators.py
│
├── dashboard/
│   ├── Home.py                     # Streamlit entry point
│   └── pages/
│       ├── 1_Discover.py
│       ├── 2_Influencers.py
│       ├── 3_Messages_Review.py
│       └── 4_Outreach_Tracker.py
│
├── tests/
│   ├── unit/
│   │   ├── test_filtering.py
│   │   ├── test_validation.py
│   │   ├── test_duplicate_guard.py
│   │   └── test_message_constraints.py
│   ├── integration/
│   │   ├── test_discovery_pipeline.py
│   │   ├── test_llm_provider.py
│   │   └── test_outreach_dry_run.py
│   └── conftest.py
│
├── data/
│   ├── raw/                        # Original source exports; gitignored
│   ├── processed/                  # Normalized outputs; gitignored
│   └── exports/                    # CSV exports; gitignored
│
├── docs/
│   ├── architecture.md
│   ├── data_dictionary.md
│   └── screenshots/
│
├── scripts/
│   ├── import_influencers.py
│   └── export_dataset.py
│
├── .env.example
├── .gitignore
├── alembic.ini                     # Optional: database migrations
├── pyproject.toml                  # Dependencies and tool configuration
├── requirements.txt
├── README.md
└── run.py                          # Optional local development launcher
```

**Build the essential folders first.** You do not need to create every empty file on day one. Add each module when its milestone begins. For the first working version, the most important modules are discovery, filtering, enrichment, LLM, outreach, database, dashboard, and tests.

---

## 5. Data model

Use one canonical schema regardless of where a creator was discovered.

### Influencer record

| Field | Type | Notes |
|---|---|---|
| id | Integer / UUID | Internal primary key |
| name | String | Creator/channel display name |
| platform | String | YouTube, Instagram, TikTok, etc. |
| profile_url | String | Canonical public profile URL |
| platform_user_id | String | Platform-specific ID, if available |
| follower_count | Integer / null | Preserve null if not available |
| engagement_rate | Float / null | Only when computed from valid data |
| engagement_method | String / null | Explain the formula and source |
| niche | String | E.g. beauty, fitness, technology |
| content_themes | JSON / text | Topics extracted from public content |
| contact_email | String / null | Null internally; show `Not Found` in UI/export |
| website | String / null | Public website, if available |
| audience_age | String / null | Only if explicitly available |
| audience_gender | String / null | Only if explicitly available |
| audience_geography | String / null | Only if explicitly available |
| source_name | String | Where the record came from |
| source_url | String | Evidence / source page |
| discovered_at | DateTime | Discovery timestamp |
| last_verified_at | DateTime / null | Last validation timestamp |
| filter_status | String | passed / failed / needs_review |
| filter_reasons | JSON / text | Human-readable pass/fail reasons |

Store source evidence and collection timestamps. A metric without provenance is difficult to verify.

### Campaign record

Store campaign name, target niche, product/brand description, target geography (optional), follower range, minimum engagement threshold (optional), collaboration type, and campaign value proposition.

### Message record

Store influencer ID, campaign ID, message type (`email` or `instagram_dm`), subject (email only), generated body, LLM provider/model, generation timestamp, review status, and approved timestamp.

### Outreach log

Store influencer ID, campaign ID, channel, recipient, message ID, status, attempt count, provider response/reference ID (when available), sent timestamp, and error message (if any).

Add a database uniqueness constraint for the campaign + influencer + channel combination, or use a carefully designed idempotency key. This is the main protection against duplicate outreach.

---

## 6. Execution plan: milestones

Build the project in small, testable milestones. Do not start by trying to automate every platform at once.

### Milestone 1 — Project setup

**Tasks**
1. Create the repository and folder structure.
2. Create a Python virtual environment.
3. Add dependencies and `.env.example`.
4. Configure logging and settings.
5. Initialize SQLite and SQLAlchemy models.

**Deliverable:** The application starts, connects to SQLite, and loads configuration without exposing secrets.

**Acceptance check:** `pytest` runs, and a simple health endpoint returns success.

### Milestone 2 — Influencer discovery (target: 50+)

**Tasks**
1. Choose one niche for the first complete workflow: Beauty & Skincare is a practical example.
2. Define the discovery source interface.
3. Implement one permitted source first (e.g. YouTube Data API) and a CSV import adapter.
4. Search using relevant niche keywords.
5. Fetch available channel/profile metadata.
6. Normalize source results into the canonical influencer schema.
7. Deduplicate by platform + platform user ID; use canonical profile URL only as a fallback.
8. Store raw source responses separately from normalized records.

**Deliverable:** At least 50 real, traceable discovered creator records for the test run.

**Acceptance check:** Every record has a source and profile URL. Unknown metrics remain null rather than being fabricated.

**Important:** YouTube is a practical first source because it has an official Data API. The API does not expose every field required by the assignment, especially contact email and private audience analytics. Use permitted public sources or a clearly labeled manual/CSV enrichment step for missing fields. Do not claim that YouTube discovery alone provides all mandatory fields.

### Milestone 3 — Filtering and classification

Implement one complete category first. Example Beauty & Skincare rules:

- Niche/content relevance: creator content should be meaningfully related to beauty or skincare.
- Follower count: 5,000–100,000, as defined in the assignment.
- Platform: initially YouTube (extend later).
- Engagement: use only a documented, consistently calculated metric when sufficient public data exists.
- Brand fit: use transparent keyword/rule-based checks first; optionally add an LLM-assisted relevance score for review.

**Example deterministic logic**

```python
def evaluate_influencer(influencer):
    reasons = []

    if influencer.follower_count is None:
        reasons.append("Follower count unavailable")
    elif not 5_000 <= influencer.follower_count <= 100_000:
        reasons.append("Outside follower-count range")

    if not influencer.niche or influencer.niche.lower() not in {
        "beauty", "skincare"
    }:
        reasons.append("Content is not classified as beauty/skincare")

    if influencer.engagement_rate is None:
        reasons.append("Engagement rate unavailable")

    if reasons:
        return {"status": "needs_review", "reasons": reasons}

    return {"status": "passed", "reasons": ["Meets configured rules"]}
```

This is an illustrative starting point. Decide whether missing engagement should mean `failed` or `needs_review` based on the campaign policy. Do not silently treat missing data as zero or as a pass.

**Deliverable:** Each creator has a `passed`, `failed`, or `needs_review` result with reasons.

### Milestone 4 — Profile enrichment

**Tasks**
1. Check the creator's public profile and linked website where access is permitted.
2. Extract publicly displayed contact information only.
3. Extract content themes from available titles, descriptions, or public posts.
4. Store the evidence URL and timestamp for each enrichment result.
5. Set unavailable email to `Not Found` in output.
6. Keep audience age, gender, and geography null unless a reliable source explicitly provides them.

**Deliverable:** Shortlisted creators have the required available profile metrics, niche/content context, and a contact-email status.

**Acceptance check:** No guessed email addresses; missing data is visible and auditable.

### Milestone 5 — AI personalization

Generate two distinct messages for each qualified creator.

**Email requirements**
- 60–90 words.
- Mention a real content theme or verified personalization signal.
- Explain why the creator's audience/content is relevant.
- State a clear collaboration idea and value proposition.
- Avoid pretending that the brand has watched a specific post if that evidence is unavailable.

**Instagram DM requirements**
- 15–30 words.
- Short, natural and creator-specific.
- No generic mass-message text.

**Prompt design**

```text
SYSTEM:
You write concise, respectful creator collaboration outreach.
Use only the facts supplied in the creator and campaign data.
Never invent a recent post, audience demographic, metric, relationship,
brand claim, or personal detail.
If a personalization signal is missing, use another verified signal.
Return valid JSON only.

USER:
Campaign:
- Brand: {brand_name}
- Product: {product_description}
- Collaboration type: {collaboration_type}
- Value proposition: {value_proposition}

Creator:
- Name: {name}
- Niche: {niche}
- Platform: {platform}
- Verified content themes: {content_themes}
- Verified recent content: {recent_content_or_not_available}

Return:
{
  "email_subject": "...",
  "email_body": "60-90 words",
  "instagram_dm": "15-30 words",
  "personalization_signals": ["..."]
}
```

**Validation after generation**
- Parse the output as JSON.
- Count email and DM words in Python.
- Check required fields and prohibited invented claims.
- Retry once with a correction instruction if word limits or structure fail.
- If validation still fails, mark the message `needs_review`; never send it automatically.

**Deliverable:** Two validated messages for each qualified influencer, with the LLM provider/model recorded.

### Milestone 6 — Outreach sending and safety

Implement two modes:

**A. Dry-run mode (default)**
- Select records with a valid email.
- Load the approved email message.
- Simulate the send operation.
- Save `dry_run` status and timestamp.
- Show the message in the dashboard.

**B. Real email mode (optional)**
- Configure Gmail API OAuth.
- Require a human approval action.
- Send only to a valid, explicitly sourced email.
- Save the provider response and delivery attempt.
- Handle authentication errors, quota errors, and transient failures.
- Do not retry blindly after an uncertain send result; check the log first.

For Instagram DMs, create a copy-ready manual workflow. The assignment explicitly says not to bypass platform restrictions when automated sending is unavailable.

**Duplicate prevention**
- Before sending, query the outreach log for the same campaign, influencer and channel.
- If a prior successful send exists, block another send.
- Use an idempotency key or unique database constraint.
- Record failed attempts separately from successful sends.

**Deliverable:** A working dry-run workflow, an auditable outreach log, and an optional guarded Gmail integration.

### Milestone 7 — Dashboard and exports

Create four simple dashboard pages:

1. **Discover:** select niche/source and run discovery.
2. **Influencers:** view profiles, metrics, source links, filter status and reasons.
3. **Messages & Review:** inspect/edit/approve email and DM messages.
4. **Outreach Tracker:** view pending, dry-run, sent, failed and duplicate-blocked records.

Add CSV export for the influencer dataset and outreach tracker.

**Deliverable:** A reviewer can demonstrate the full pipeline without reading the source code.

### Milestone 8 — Testing and final submission

Test:
- Invalid or missing API keys.
- Empty discovery results.
- Duplicate profiles.
- Missing follower count and email.
- Invalid metric values.
- LLM timeout, malformed JSON and rate-limit errors.
- Email word count and DM word count.
- Duplicate send attempts.
- Gmail authentication failure.
- Dry-run mode with no real network send.

Prepare:
- GitHub repository.
- README and setup instructions.
- Dataset of at least 50 traceable profiles.
- Sample generated email and DM messages.
- Outreach tracker export.
- Screenshots or short demo video.
- List of APIs, tools, and known limitations.

---

## 7. Filtering design and engagement-rate caveat

The assignment asks for follower count and engagement rate. These values are not equally available across platforms.

For YouTube, a possible public-data engagement proxy is:

```text
Engagement proxy (%) =
((likes + comments) / views) * 100
```

Calculate it over a defined set of recent videos, such as the latest 5–10 eligible videos, and store the sample size, date range, formula, and source. This is a **views-based interaction proxy**, not the conventional follower-based engagement rate. Label it accurately.

A follower-based proxy might be:

```text
Follower-based engagement (%) =
((average likes + average comments) / followers) * 100
```

Use this only when the necessary metrics are genuinely available and comparable. Do not compare different formulas as though they were the same metric. YouTube API visibility, hidden counts, Shorts, and outlier videos can affect the calculation.

For the first version, make engagement a configurable rule:
- `passed`: valid metric meets the campaign threshold.
- `failed`: valid metric is below the threshold.
- `needs_review`: metric unavailable or insufficient sample.

The assignment does not prescribe a minimum engagement percentage. Choose and document a threshold for the demo rather than presenting it as an assignment rule.

---

## 8. Limitations, risks, and practical solutions

| Limitation / issue | Why it happens | Practical solution |
|---|---|---|
| Instagram/TikTok discovery is restricted | Official APIs have access, permission and account-type constraints; public scraping can violate terms or break | Start with YouTube Data API, permitted directories, creator opt-in lists and CSV imports. Add other sources only after checking their current terms and permissions. |
| Reaching 50 profiles is not guaranteed by one query | Search relevance, API quotas, niche size and pagination affect results | Use several relevant keyword searches, paginate within quota, deduplicate, and supplement with permitted sources. Report the actual count; never pad with fake records. |
| Contact email is missing | Many creators do not publish an email, or hide it behind platform UI | Check linked public websites and business-contact pages where permitted. Store evidence. Mark `Not Found` if unavailable. |
| Audience age/gender/location is unavailable | These are often private analytics visible only to the creator/account owner | Keep null / `Not Available`. Do not infer demographics from photos, names, language, or content. |
| Engagement rate is inconsistent | Platforms expose different metrics and definitions; some values may be hidden | Store formula, source, sample size and collection date. Compare only like-for-like metrics. |
| Profile data becomes stale | Follower counts and content change over time | Store `last_verified_at`; refresh before a campaign and display the data collection date. |
| LLM invents personalization | Models can hallucinate details not present in the prompt | Ground prompts in verified fields, require structured JSON, validate output, and add human review. |
| LLM word count is wrong | Models do not reliably obey exact length constraints | Count words in Python; retry once; route persistent failures to review. |
| Free LLM quota is exceeded | Free plans have request/token limits that can change | Use batching carefully, short prompts, caching, retry with backoff, and a provider switch. Never retry continuously on HTTP 429. |
| LLM provider/model changes | Model names and availability can change | Keep provider/model in environment configuration and isolate integrations behind `LLMProvider`. |
| Email sending fails | OAuth expiry, API quota, invalid recipient, spam filters or network errors | Use dry-run first, refresh OAuth safely, validate addresses, log provider responses, and use bounded retries only for known transient errors. |
| Duplicate outreach | A user reruns a campaign or a request times out after sending | Enforce a unique campaign/creator/channel key, check status before send, and treat uncertain send outcomes as `unknown` until reconciled. |
| Instagram DM cannot be sent automatically | API access and platform rules may not permit the intended workflow | Generate the DM and provide a copy-ready manual send action. Do not automate browser login or bypass platform controls. |
| Scraping breaks | HTML changes, anti-bot controls, CAPTCHAs, rate limits | Prefer official APIs and stable imports. Keep each source in a separate adapter; stop and surface access errors rather than evading controls. |
| Personal data / privacy risk | Emails and profile data are personal information | Collect only necessary public business-contact data, record source and purpose, restrict access, provide deletion capability, and follow applicable privacy and anti-spam rules. |
| SQLite limits concurrent workloads | SQLite is suitable for a local demo but has limited write concurrency | Keep SQLite for the assignment. Move to PostgreSQL only if concurrent users or deployment needs justify it. |
| Discovery sources return duplicates | Same creator may appear under multiple keywords or platforms | Deduplicate by platform ID, then canonical URL; preserve source references and merge only when identity is clear. |

### Important legal and platform note

Publicly viewable does not automatically mean unrestricted to scrape, store, or contact. Check each platform's current terms, API policies, data-protection requirements, and applicable anti-spam rules before collecting or sending. Use official APIs and permitted sources wherever possible. This README is an engineering plan, not legal advice.

---

## 9. Error handling and reliability standards

Use explicit statuses rather than silently dropping failed records.

Suggested statuses:

- Discovery: `queued`, `success`, `partial`, `failed`.
- Enrichment: `complete`, `partial`, `not_found`, `failed`.
- Filtering: `passed`, `failed`, `needs_review`.
- Message: `generated`, `approved`, `rejected`, `needs_review`, `generation_failed`.
- Outreach: `pending`, `dry_run`, `sent`, `failed`, `unknown`, `duplicate_blocked`, `manual_required`.

Recommended engineering practices:
1. Set timeouts on all external requests.
2. Retry only transient failures with exponential backoff and a maximum attempt count.
3. Respect `Retry-After` and provider rate-limit headers.
4. Do not retry invalid credentials or permission errors indefinitely.
5. Use structured logs with influencer ID, campaign ID, provider and operation.
6. Keep raw source data separate from normalized records.
7. Validate all external data at the boundary using Pydantic.
8. Make each pipeline stage restartable.
9. Record partial success instead of losing the entire batch.
10. Keep real email sending disabled by default.

---

## 10. Local setup instructions

### Prerequisites

- Python 3.11 or later.
- Git.
- A Groq or Gemini API key for AI message generation.
- Optional YouTube Data API key for discovery.
- Optional Google Cloud project and Gmail API OAuth credentials for real email sending.

### Installation

```bash
# 1. Clone the repository
git clone <your-repository-url>
cd micro-influencer-outreach

# 2. Create a virtual environment
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# macOS / Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your local environment file
# Windows PowerShell
Copy-Item .env.example .env

# macOS / Linux
cp .env.example .env

# 5. Edit .env and add the API key/provider configuration
```

### Suggested initial `requirements.txt`

```text
fastapi
uvicorn[standard]
streamlit
sqlalchemy
pydantic
pydantic-settings
python-dotenv
pandas
httpx
groq
google-genai
pytest
pytest-cov
email-validator
google-api-python-client
google-auth-oauthlib
google-auth-httplib2
```

Install only the integrations you actually use if you want a smaller environment.

### Run the backend

```bash
uvicorn app.main:app --reload
```

Open the FastAPI interactive docs at:

```text
http://127.0.0.1:8000/docs
```

### Run the dashboard

```bash
streamlit run dashboard/Home.py
```

### Run tests

```bash
pytest -q
```

### Export the dataset

```bash
python scripts/export_dataset.py
```

The commands above assume you implement the corresponding entry points during the milestones. Do not expect them to work before those modules exist.

---

## 11. Suggested API design

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/health` | Application health |
| POST | `/discovery/run` | Start a discovery job |
| GET | `/influencers` | List/search/filter influencers |
| GET | `/influencers/{id}` | Get one creator |
| POST | `/campaigns` | Create a campaign |
| GET | `/campaigns` | List campaigns |
| POST | `/campaigns/{id}/filter` | Run filtering |
| POST | `/campaigns/{id}/messages/generate` | Generate messages for qualified creators |
| POST | `/messages/{id}/approve` | Approve a message |
| POST | `/outreach/{message_id}/dry-run` | Simulate delivery |
| POST | `/outreach/{message_id}/send` | Send approved email when explicitly enabled |
| GET | `/outreach/logs` | View outreach history |
| GET | `/exports/influencers` | Export influencer CSV |

Keep sending endpoints protected and disabled unless the user has configured the required credentials and explicit send setting.

---

## 12. LLM provider architecture

The business layer should call one common interface, not Groq or Gemini directly.

Conceptual interface:

```python
from typing import Protocol

class LLMProvider(Protocol):
    def generate(self, system_prompt: str, user_prompt: str) -> str:
        ...
```

Implement:
- `GroqProvider.generate(...)`
- `GeminiProvider.generate(...)`

Then select the provider in a factory using `LLM_PROVIDER`.

This makes it possible to switch providers by changing `.env`, without rewriting filtering, message validation, API routes, or dashboard code.

Keep provider-specific error handling inside the provider adapter. Convert provider errors into application-level exceptions such as `LLMRateLimitError`, `LLMAuthenticationError`, and `LLMGenerationError`.

---

## 13. Prompt quality and message validation

The LLM should receive a compact, evidence-based creator profile, not an entire unverified scrape.

Before generation:
- Confirm creator name and profile URL.
- Include only verified content themes.
- Include recent content only when a source URL and date are available.
- Exclude unavailable audience data.
- Include campaign value proposition and collaboration type.

After generation:
- Verify JSON structure.
- Verify email is 60–90 words.
- Verify DM is 15–30 words.
- Reject placeholders such as `[insert name]`.
- Check that the personalization signals appear in the supplied creator data.
- Save model/provider and prompt version.
- Require a human to approve messages before sending.

Do not ask the model to invent an email address or estimate missing audience demographics.

---

## 14. Suggested demo scenario

Use one campaign to demonstrate the end-to-end flow:

**Campaign:** Beauty & Skincare product launch  
**Target:** Micro-influencers with 5,000–100,000 followers  
**Discovery target:** At least 50 real creator records  
**Shortlist:** Records meeting the configured rules  
**Enrichment:** Public contact details and content themes, with unavailable values labeled  
**Personalization:** One 60–90 word email and one 15–30 word DM per qualified creator  
**Sending:** Dry-run by default; optional approved Gmail send  
**Tracking:** Status, timestamp, recipient, message, and duplicate protection

During the demo, show:
1. The discovery source and 50+ collected records.
2. A creator passing and another failing, with clear reasons.
3. A creator with missing email correctly marked `Not Found`.
4. The generated email and DM with their word counts.
5. A human approval step.
6. A dry-run send and the resulting outreach log.
7. A second attempt being blocked as a duplicate.

This demonstrates the engineering workflow even if some platform-specific data is unavailable.

---

## 15. Definition of done / assignment checklist

- [ ] A working local application with clear setup instructions.
- [ ] At least 50 genuine discovered influencer records.
- [ ] Source name/URL and collection timestamp for records.
- [ ] One complete niche filtering category.
- [ ] Pass/fail/needs-review status with reasons.
- [ ] Enriched shortlisted profiles.
- [ ] Missing emails shown as `Not Found`.
- [ ] No fabricated metrics or guessed contact details.
- [ ] Personalized email pitch for every qualified creator.
- [ ] Personalized Instagram DM for every qualified creator.
- [ ] Programmatic word-count validation.
- [ ] Dry-run email sending.
- [ ] Optional guarded Gmail integration.
- [ ] Manual/copy-ready Instagram DM workflow.
- [ ] Outreach log and duplicate prevention.
- [ ] CSV export of dataset and tracker.
- [ ] Unit and integration tests.
- [ ] Screenshots or demo video.
- [ ] Documented APIs, sources, prompts, filtering rules and limitations.

---

## 16. Official documentation and useful resources

Check these official pages when implementing because API terms, model availability, and free-tier quotas can change:

- [Groq API quickstart](https://console.groq.com/docs/quickstart)
- [Groq text generation](https://console.groq.com/docs/text-chat)
- [Groq rate limits](https://console.groq.com/docs/rate-limits)
- [Google Gemini API pricing and free tier](https://ai.google.dev/gemini-api/docs/pricing)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)
- [Google Gen AI Python SDK](https://github.com/googleapis/python-genai)
- [YouTube Data API documentation](https://developers.google.com/youtube/v3)
- [FastAPI documentation](https://fastapi.tiangolo.com/)
- [Streamlit documentation](https://docs.streamlit.io/)
- [SQLAlchemy documentation](https://docs.sqlalchemy.org/)
- [Google Gmail API documentation](https://developers.google.com/gmail/api)

---

## 17. Final implementation advice

Build a **reliable vertical slice** before expanding the number of platforms:

1. Discover creators from one permitted source.
2. Normalize and save them.
3. Filter one niche.
4. Enrich available public information.
5. Generate and validate messages with Groq or Gemini.
6. Review and dry-run outreach.
7. Track the result.

Once that flow works, add more discovery adapters and optional Gmail sending. A transparent system with 50 real records, traceable data, clear limitations, robust validation, and safe outreach is stronger than a broad scraper that produces unreliable or fabricated data.
