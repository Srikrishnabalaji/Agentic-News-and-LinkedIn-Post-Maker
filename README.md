# QuantrixLabs LinkedIn Agent

An agentic system that, every morning, scans trusted cybersecurity news,
turns the most public-relevant stories into ready-to-edit LinkedIn drafts
(in the voice of QuantrixLabs' Chief Social Media Handler), finds free
images, emails you a digest, and gives you a web app to edit, preview, and
approve — then copy into LinkedIn yourself.

> Posting is **human-in-the-loop**: the app prepares finished drafts; a person
> reviews, edits, and publishes. The architecture has a reserved slot for the
> LinkedIn API so automated publishing can be added later with no schema change.

---

## How it works

```
 11 AM cron ─► scrape RSS (10 trusted sources)
              └► rank (recency · public impact · novelty · authority)
                 └► top 5 ─► Claude writes posts (picks format, hashtags, image call)
                            └► find free images (Unsplash/Pexels/Wikimedia/article)
                               └► save to DB ─► email digest ─► review in web app
```

- **Novelty:** a topic posted in the last 7 days is skipped — unless it is
  flagged *pivotal* (e.g. an actively-exploited zero-day), which is covered
  regardless. History is retained ~14 days.
- **Offline-friendly:** with no API keys the pipeline still runs end-to-end
  using a deterministic mock generator and keyless image sources, so you can
  test everything before wiring up accounts.

## Tech stack

| Layer | Choice |
|---|---|
| Backend | Python 3.11, FastAPI, SQLAlchemy 2 |
| Scraping | feedparser + httpx + BeautifulSoup |
| AI | Anthropic Claude (`claude-sonnet-4-6` default; set `claude-opus-4-8` for best writing) |
| DB | SQLite locally · PostgreSQL on Railway |
| Email | Gmail SMTP (App Password) + Jinja2 |
| Frontend | React 19 + Vite + TailwindCSS |
| Deploy | Docker on Railway (one web service + one cron service + Postgres) |

---

## Local development

### 1. Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate            # Windows  (source .venv/bin/activate on macOS/Linux)
pip install -r requirements.txt
copy .env.example .env            # then fill in keys (optional for a mock run)
uvicorn app.main:app --reload --port 8000
```

Run the daily pipeline once (what the cron does):

```bash
python -m app.cli run
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173 (proxies /api to :8000)
```

### Tests / smoke checks

```bash
cd backend
python -m tests.smoke_scraper     # live RSS across all sources
python -m tests.smoke_ranker      # scoring logic assertions
python -m tests.smoke_generator   # generation (mock unless ANTHROPIC_API_KEY set)
python -m tests.smoke_images      # live Wikimedia image search
python -m tests.smoke_email       # renders tests/_digest_preview.html
```

---

## Configuration

All config is via environment variables — see [`backend/.env.example`](backend/.env.example).
Everything except the database is optional for a local mock run.

### Gmail App Password (for the digest email)

1. Enable 2-Step Verification on the `quantrixlabs@gmail.com` Google account.
2. Go to **Google Account → Security → App passwords**.
3. Generate a password for "Mail"; copy the 16-character value.
4. Set `GMAIL_ADDRESS=quantrixlabs@gmail.com` and `GMAIL_APP_PASSWORD=<that value>`.

App Passwords are revocable and scoped to mail only — safer than your real
password, and they bypass the interactive login that blocks plain SMTP.

### Image API keys (optional)

- **Unsplash:** register a free app at unsplash.com/developers → `UNSPLASH_ACCESS_KEY`.
- **Pexels:** free key at pexels.com/api → `PEXELS_API_KEY`.
- Without either, the agent still sources images from **Wikimedia Commons**
  (no key) and each article's own lead image (flagged "verify reuse rights").

---

## Deploy to Railway

The repo builds as a **single Docker image** that serves both the API and the
compiled frontend. You create three things in your Railway project:

### 1. Postgres
Add the **PostgreSQL** plugin. Railway sets `DATABASE_URL` automatically;
reference it from the services below.

### 2. Web service (the app + API)
- New service → Deploy from this repo. Railway picks up `railway.json` / `Dockerfile`.
- **Variables:** `ANTHROPIC_API_KEY`, `ANTHROPIC_MODEL`, `GMAIL_ADDRESS`,
  `GMAIL_APP_PASSWORD`, `NOTIFICATION_EMAIL`, `FRONTEND_URL` (this service's
  public URL), `UNSPLASH_ACCESS_KEY`/`PEXELS_API_KEY` (optional), and a
  reference to `DATABASE_URL`.
- Start command (from `railway.json`): `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

### 3. Cron service (the 11 AM run)
- New service → same repo/image.
- **Start command:** `python -m app.cli run`
- **Cron schedule:** `0 11 * * *`
- Same variables as the web service (it shares the database).

> ⚠️ **Timezone:** Railway cron runs in **UTC**. `0 11 * * *` fires at 11:00 UTC.
> Adjust the hour to hit 11 AM in your local timezone (e.g. for US Eastern in
> summer / EDT use `0 15 * * *`). Tell me your timezone and I'll set it exactly.

When the cron finishes it writes the day's drafts to Postgres and emails the
digest; open the web service URL to review.

---

## Adding automated LinkedIn posting later

The data model already reserves `posts.linkedin_post_id`. To go live:

1. Register a LinkedIn developer app (Community Management / "Share on
   LinkedIn" product) and complete OAuth for the QuantrixLabs page.
2. Store the OAuth token (add a small `credentials` table or a Railway secret).
3. Add `POST /posts/{id}/publish` that calls the LinkedIn UGC/Posts API and
   saves the returned id into `linkedin_post_id`.
4. Swap the frontend's **Copy text** for a **Publish** button.

No other architectural changes are required.

---

## Project layout

```
backend/
  app/
    config.py            settings (env vars)
    db.py  models.py      SQLAlchemy (SQLite/Postgres)
    scraper/             rss.py · article.py · sources.py
    ranking/scorer.py    deterministic story scoring
    generator/           brand.py · post.py (Claude) · images.py
    notify/email.py      Gmail SMTP digest + Jinja2 template
    routes/              posts · images · runs
    pipeline.py          the daily orchestrator
    cli.py               `python -m app.cli run` (cron entrypoint)
    main.py              FastAPI app (+ serves built frontend)
  tests/                 smoke_*.py
frontend/
  src/
    api.ts  types.ts
    components/          PostEditor · LinkedInPreview · ImagePicker · HashtagEditor
    pages/               Dashboard · History
    App.tsx
Dockerfile  railway.json
```
