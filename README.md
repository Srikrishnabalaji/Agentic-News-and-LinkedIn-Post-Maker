# QuantrixLabs LinkedIn Agent

An agentic content pipeline that monitors trusted cybersecurity and finance news sources, generates polished LinkedIn drafts in QuantrixLabs' brand voice, and surfaces them in a review interface for a human editor to approve and publish.

Posting is **human-in-the-loop** by design. The agent handles research, writing, and image sourcing; a person makes the final call on what goes live. The architecture reserves a slot for direct LinkedIn API publishing when that integration is ready.

---

## What it does

Every morning the pipeline runs automatically:

1. **Scrapes** RSS feeds across trusted cybersecurity and finance sources
2. **Ranks** stories by recency, public impact, novelty, and source authority
3. **Generates** up to 5 LinkedIn posts — selecting the appropriate format (listicle, hot take, explainer, etc.), hashtags, and image recommendations
4. **Sources images** from Unsplash, Pexels, Wikimedia Commons, or the article itself
5. **Emails** a digest so the editor knows new drafts are ready
6. **Saves** everything to the database for review

A topic covered in the last 7 days is automatically skipped to avoid repetition — unless it is flagged *pivotal* (e.g. an actively-exploited zero-day), in which case it is always covered.

---

## The editor interface

The web app gives the editor full control over each draft before anything goes live:

- **Dashboard** — view today's generated drafts by category, edit post body and headline, rephrase with AI (punchy / formal / shorter), pick or swap images, manage hashtags, and preview exactly how the post will render on LinkedIn
- **History** — browse all past drafts with status tracking; open any previous post back in the editor
- **Search** — search across saved posts or run a live web search to pull in new stories on demand
- **Sources** — manage the RSS feeds the pipeline monitors
- **Candidate drawer** — pull additional stories into the dashboard outside of the scheduled run
- **Metrics** — record and track post performance (impressions, likes, comments) after publishing

Posts move through a `draft → approved → posted` workflow. The editor copies the final text and image to LinkedIn manually; a tagging reminder surfaces if the post contains `@mentions`.

---

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2 |
| Scraping | feedparser + httpx + BeautifulSoup |
| AI | Gemini · OpenAI · Anthropic Claude (tried in order, first available key wins) |
| Web search | Tavily |
| Images | Unsplash · Pexels · Wikimedia Commons · article lead image |
| Database | SQLite (local) · PostgreSQL (production) |
| Email | Gmail SMTP + Jinja2 |
| Frontend | React 19, Vite, Tailwind CSS |
| Deployment | Docker on Railway (web service + cron service + Postgres) |

---

## Setup

All configuration is via environment variables. Copy `backend/.env.example` to `backend/.env` and fill in the relevant values. See the example file for the full list.

### Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate       # Windows — use source .venv/bin/activate on macOS/Linux
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

To run the pipeline manually (equivalent to the scheduled cron):

```bash
python -m app.cli run
```

### Frontend

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173 — proxies /api requests to :8000
```

---

## Deployment (Railway)

The repo builds as a single Docker image serving both the API and the compiled frontend.

1. **Postgres** — add the PostgreSQL plugin; Railway injects `DATABASE_URL` automatically.
2. **Web service** — deploy from this repo. Set all required environment variables from `.env.example` in the Railway Variables tab.
3. **Cron service** — same image, start command `python -m app.cli run`, schedule `0 11 * * *`.

Railway cron runs in UTC — adjust the hour to match your target local time.

---

## LinkedIn API integration (roadmap)

The data model already reserves `posts.linkedin_post_id`. When ready:

1. Register a LinkedIn developer app with the Community Management product and complete OAuth for the QuantrixLabs page.
2. Store the OAuth token as a Railway secret.
3. Add `POST /posts/{id}/publish` — calls the LinkedIn UGC Posts API and saves the returned ID.
4. Replace the **Copy text** button with **Publish**.

No schema or architectural changes are required beyond the above.

---

## Project layout

```
backend/
  app/
    config.py            environment variable settings
    db.py  models.py     SQLAlchemy models (SQLite / Postgres)
    scraper/             rss.py · article.py · sources.py
    ranking/scorer.py    deterministic story scoring
    generator/           brand.py · post.py · build.py · images.py
    notify/email.py      Gmail digest + Jinja2 template
    routes/              posts · candidates · search · sources · images · runs
    pipeline.py          daily orchestrator
    cli.py               cron entrypoint
    main.py              FastAPI app (also serves compiled frontend)
  tests/                 smoke_*.py
frontend/
  src/
    api.ts  types.ts
    components/          PostEditor · LinkedInPreview · ImagePicker · HashtagEditor
                         · FormattingToolbar · CandidateDrawer · MetricsPanel
    pages/               Dashboard · History · Search · Sources
    App.tsx
Dockerfile  railway.json
```
