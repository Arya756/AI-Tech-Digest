# AI Tech Digest Agent

> **Your twice-daily 3-minute AI briefing. Read less, know more. 🎙️**
>
> A fully autonomous AI agent that fetches, ranks, summarizes, and delivers the top 5 AI tech stories — as a formatted Telegram message and a human-quality voice briefing — in English or Hindi, twice a day.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Tech Stack](#tech-stack)
4. [Complete Workflow](#complete-workflow)
5. [Module Breakdown](#module-breakdown)
6. [Deduplication System](#deduplication-system)
7. [Voice Engine](#voice-engine)
8. [Telegram Bot](#telegram-bot)
9. [Scheduler](#scheduler)
10. [Landing Page](#landing-page)
11. [Difficulties Faced & How We Solved Them](#difficulties-faced--how-we-solved-them)
12. [Setup & Installation](#setup--installation)
13. [Deployment](#deployment)
14. [Environment Variables](#environment-variables)
15. [Project Structure](#project-structure)

---

## Project Overview

AI Tech Digest is a **production-grade autonomous news agent** built with LangGraph. Every day it:

1. Pulls fresh articles from **12 high-signal RSS sources** (OpenAI Blog, Google AI, Microsoft AI, Meta AI, TensorFlow, ArXiv, Hacker News, TechCrunch, and more)
2. Runs each article through an **LLM-powered scoring pipeline** — scoring innovation, impact, and credibility
3. Selects the **Top 5 stories** with category-diversity enforcement (no single topic dominates)
4. Translates the digest to **Hindi** using the same LLM
5. Generates **human-quality voice briefings** in both English (Ava Neural) and Hindi (Madhur Neural)
6. Delivers the text digest + audio to each subscriber on **Telegram** twice a day (AM and PM cycle)
7. **Never repeats** a story — permanently tracking every sent article via MongoDB

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        LangGraph Pipeline                        │
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  NODE 1  │───▶│  NODE 2  │───▶│  NODE 3  │───▶│  NODE 4  │  │
│  │  FETCH   │    │ ANALYZE  │    │   RANK   │    │  OUTPUT  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│  12 RSS feeds   LLM scoring     Top-5 select    Format digest  │
│  Reddit API     Parallel exec   Category caps   Hindi translate │
│  Dedup checks   22hr cache      Source limits                   │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Voice Engine (edge-tts)                     │
│                                                                  │
│   EN Digest (.txt) ──▶ Ava Neural ──▶ digest_YYYY-MM-DD_AM_en.mp3│
│   HI Digest (.txt) ──▶ Madhur Neural ─▶ digest_YYYY-MM-DD_AM_hi.mp3│
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Telegram Bot + Hourly Scheduler                  │
│                                                                 │
│   Scheduler wakes every hour at the top of the hour (:00)       │
│   ──▶ Finds subscribers for that hour                            │
│   ──▶ Generates digest if not done yet (lazy init)               │
│   ──▶ Sends text + voice in user's language                      │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    MongoDB (Four Collections)                     │
│                                                                 │
│   subscribers   → chat_id, language, delivery_time, active        │
│   history       → link, fingerprint (permanent dedup ledger)      │
│   daily_digests → date_str, lang, content, created_at             │
│   digest_audio  → (GridFS) filename, data, created_at             │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) | Stateful, multi-node AI pipeline |
| **LLM** | [Groq API](https://groq.com/) — `llama-3.3-70b-versatile` | Article scoring, summarization, translation |
| **RSS Parsing** | `feedparser` + `requests` | Fetching articles from 15 sources (12 RSS + Reddit `.rss` + Hacker News Algolia API) |
| **Text-to-Speech** | [edge-tts](https://github.com/rany2/edge-tts) — Microsoft Neural | Voice briefings in EN & HI |
| **Thumbnails** | [Pillow](https://python-pillware.org/) (CPU-only vector art) | Per-story cover images — category colors + topic motifs, zero-cost, no external image API |
| **Telegram** | [python-telegram-bot v22](https://python-telegram-bot.org/) | Delivery, bot commands, inline keyboards, media groups |
| **Database** | [MongoDB](https://www.mongodb.com/) + PyMongo | Subscribers + deduplication ledger |
| **Scheduling** | Custom IST time-check loop (in `run.py`) | Hourly daemon, drift-free, timezone-correct |
| **Frontend** | Next.js 16 + Tailwind CSS + Framer Motion | Landing page |
| **Language** | Python 3.12+ | Core backend |
| **Config** | `Procfile` (`python run.py`) | Locks the Render start command |

---

## Complete Workflow

### Step 1 — User Subscribes

```
User visits landing page
  ──▶ Clicks "Subscribe Free"
  ──▶ Opens Telegram to @aitechdigest_bot
  ──▶ Taps START → bot receives /start
  ──▶ Bot saves user to MongoDB with defaults
  ──▶ Bot presents language choice: [English 🇬🇧] [Hindi 🇮🇳]
  ──▶ User taps language → saved to DB
  ──▶ Bot presents time choice: [07:00 AM] [08:00 AM] [09:00 AM]
  ──▶ User taps time → saved to DB
  ──▶ "✅ All set! You'll receive your AI Tech Digest twice daily: Morning at 08:00 AM, Evening at 08:00 PM."
```

### Step 2 — Scheduler Wakes Up (Every Hour)

```
1. Check: are there any active subscribers for this hour?
2. If NO → go back to sleep
3. If YES →
   a. Check: does today's digest file exist on disk?
   b. If NO → run full LangGraph pipeline (FETCH → ANALYZE → RANK → OUTPUT)
   c. Check: does the voice note exist for each language?
   d. If NO → generate voice via edge-tts
   e. For each subscriber in this hour's batch:
      → Send text digest in their language
      → Send voice note in their language
      → Sleep 1 second (rate limit protection)
```

### Step 3 — LangGraph Pipeline (Runs Twice Per Day)

```
NODE 1: FETCH
  ├─ Pull from 15 sources (12 RSS + Reddit `.rss` + Hacker News Algolia API) in parallel
  ├─ Apply age filters (lab blogs: 7 days, news: 2 days)
  ├─ Check MongoDB history (permanent dedup)
  ├─ Check title fingerprint (cross-source dedup)
  └─ Returns ~40-80 raw candidate articles

NODE 2: ANALYZE (Parallel LLM calls, 4 threads)
  ├─ Stage 0: Keyword pre-filter (zero tokens — removes deals, coupons)
  ├─ For each article, call Groq LLM with structured prompt (dedup against MongoDB `history` so repeated stories are skipped)
  │   └─ Returns JSON: {keep, category, summary, context, innovation(1-5),
  │                      impact(1-5), credibility(1-5), noise(0-1), why_it_matters}
  └─ No file-based cache — deduplication is handled by the MongoDB `history` ledger

NODE 3: RANK
  ├─ Compute total_score = (innovation + impact + credibility - noise*10) * source_weight
  ├─ Apply category caps: max 2 AI, 2 big_tech, 2 startup, 1 research, 1 infra
  ├─ Apply source cap: max 2 articles per source
  ├─ ArXiv and Reddit get -10% to -20% score penalty (papers rarely matter same day)
  └─ 3-pass fallback fill to always reach exactly 5 stories

NODE 4: OUTPUT
  ├─ Format English digest into clean, readable text files
  ├─ Translate to Hindi via LLM (preserves company names and formatting)
  └─ Save both as digest_YYYY-MM-DD_en.txt and digest_YYYY-MM-DD_hi.txt
```

---

## Module Breakdown

### `graph.py` — The Orchestrator
Defines the LangGraph `StateGraph` with a shared `State` TypedDict that flows through all 4 nodes. Each node reads from and writes to this shared state, keeping the pipeline clean and testable in isolation.

### `fetch_news.py` — The Ingestion Layer
- **15 sources**: 12 RSS feeds + Reddit (`.rss` Atom, no OAuth — the JSON API is blocked for bot user-agents) + Hacker News via the Algolia search API (no RSS host dependency, no auth)
- **Per-source credibility weights** (1.2x–1.8x) and daily caps
- **Title Fingerprinting**: Strips stopwords, takes first 6 meaningful words to create a semantic key — catches the same story published on multiple outlets
- **Age Filtering**: Lab blogs allowed up to 7 days old; news sites capped at 2 days
- **`_http_get()` retry helper** with exponential backoff + 429 handling, so transient Reddit/HN rate-limiting is absorbed gracefully

### `summarize.py` — The Intelligence Layer
- **Single LLM prompt per article** — scoring + summarization + categorization in one call (minimizes token usage on Groq free tier)
- **Parallel processing** via `ThreadPoolExecutor(max_workers=4)` — 4x faster than sequential
- **`rank_and_diversify()`**: Three-pass selection ensuring the daily digest is never dominated by a single topic or source

### `thumbnail.py` — The Visual Layer (zero-cost)
- **Pillow CPU-only vector art** — no external image API (keeps the bot fully autonomous + free)
- Renders a 1080×1080 cover per story with a **category-colored background** (7 categories: research, ai, ai_tools, big_tech, startup, hardware, other)
- Draws a **category glyph** + a **topic-resonant motif** (phone, megaphone, chip, rocket, brain, scan, chat) chosen from the article title's keywords
- Bundled `DejaVuSans.ttf` (SIL license) for Render portability
- Used by `telegram_bot.send_digest` to build a per-story media gallery

### `db.py` — The Database Layer
Four MongoDB collections:
- **`subscribers`**: Stores `chat_id`, `username`, `language`, `delivery_time`, `active` flag
- **`history`**: Permanent ledger — every sent article's URL and title fingerprint are stored here forever. Never expires.
- **`daily_digests`**: Stores the raw text content of the generated digests for each date and language, **plus the structured `items` list** (real category + score) so thumbnails render correct per-category colors without re-parsing text.
- **`digest_audio`**: GridFS collections (`digest_audio.files` and `digest_audio.chunks`) storing the binary voice notes (`.mp3` files) for each digest.

### `voice_engine.py` — The Audio Layer
- **Language-aware script builder**: Generates fully localized scripts — Hindi scripts use native Hindi intros (`सुप्रभात...`), transitions (`अगली खबर...`), and outros
- **`_clean_for_speech()`**: Strips URLs, emojis, category labels, markdown syntax, and score tags that sound awkward when read aloud
- **Threading safety**: Uses `threading.Thread` to run `asyncio.run()` safely if called from within an existing event loop (avoids `RuntimeError: no running event loop`)

### `telegram_bot.py` — The Delivery Layer
- **Two modes**: `--send` (broadcast) and `--bot` (interactive registration)
- **Emoji-based parser**: Parses digest files using Unicode emoji codepoints (`📰`, `🧠`, `👉`) instead of English strings — ensures both EN and HI digests are parsed correctly
- **MarkdownV2 escaping**: All dynamic text is escaped via the shared `utils.esc()` helper before sending (single implementation, reused everywhere)
- **Sequential per-story gallery**: `send_digest()` sends a thumbnail photo, then the story text (title → source → summary → tappable "Read full story" link) for each story, then the voice note — so the chat reads thumb→text→link, repeated, then audio
- **Web-page previews disabled** on text messages so only your thumbnails + clean text show (no Telegram auto link-preview clutter)
- **Guard clauses**: All handlers check for `None` on `update.message`, `update.effective_user`, etc.

### `scheduler.py` — The Background Worker
- Runs an hourly loop driven by a **custom drift-free IST time-check** (reads `ZoneInfo("Asia/Kolkata")`, triggers `hourly_job` at :00 IST — no `schedule` library, no system-timezone dependence)
- **Lazy Initialization**: Only runs the expensive pipeline if the digest files don't yet exist for today
- **Graceful failure handling**: If `run_pipeline()` fails (e.g. Groq quota), it surfaces the real error + full traceback, falls back to the **most recent stored digest** so subscribers still get content, and sends a `🚨 digest generation failed` alert to Telegram (via `ADMIN_CHAT_ID` or, if unset, the oldest subscriber) — so failures are visible without Render's paid-tier log history
- **7-day cleanup**: Automatically deletes digest and audio files older than 7 days to prevent disk exhaustion

### `run.py` — The Unified Entry Point
- Runs the Telegram Bot (main thread) + Scheduler (daemon thread) + a dummy HTTP health-check server (so Render's Free Web Service stays alive) in one process
- **Startup self-test**: On boot, pings MongoDB, validates the Telegram token, and counts active subscribers — fails loudly (aborts) if config is broken, instead of running a dead service silently
- Uses `Procfile` (`python run.py`) to lock the start command on Render

---

## Deduplication System

The system uses a **layered, two-level deduplication strategy**:

```
Level 1 — In-Session (Same Fetch)
  Tool: title fingerprint set (in-memory)
  Scope: Within a single pipeline run
  Example: "OpenAI releases GPT-5" from TechCrunch AND VentureBeat in same run
  
Level 2 — Cross-Day (MongoDB History)
  Tool: Permanent MongoDB `history` collection
  Scope: Forever — once sent, never sent again
  Keys: article URL + title fingerprint
  Example: Story sent Monday — blocked Tuesday, Wednesday, forever
```

> Note: a previous "Level 3" file-based JSON cache was removed; deduplication is now handled entirely by the MongoDB `history` collection, which is the source of truth for "already sent".

---

## Voice Engine

The voice engine produces two distinct audio styles:

**English (Ava Neural — en-US-AvaNeural)**
```
"Good morning, and welcome to your AI Tech Digest for May 16th...
 
 Story one. OpenAI launches Codex...
 
 A bit of background: Codex is an AI coding agent that...
 
 Why this matters: Developers save 10+ hours per week...
 
 That wraps up today's briefing. Stay curious, stay ahead."
```

**Hindi (Madhur Neural — hi-IN-MadhurNeural)**
```
"सुप्रभात! एआई टेक डाइजेस्ट में आपका स्वागत है...
 
 पहली खबर। OpenAI ने Codex लॉन्च किया...
 
 थोड़ी पृष्ठभूमि: Codex एक एआई कोडिंग एजेंट है...
 
 यह क्यों मायने रखता है: डेवलपर्स हर हफ्ते 10+ घंटे बचाते हैं...
 
 आज का डाइजेस्ट यहीं समाप्त होता है। धन्यवाद!"
```

---

## Telegram Bot

### User Commands

| Command | Description |
|---|---|
| `/start` | Subscribe and set language + delivery time preferences |
| `/stop` | Unsubscribe (sets `active: False` in DB) |
| `/latest` | Get today's digest immediately on demand |
| `/help` | Show all available commands |

### Registration Flow

```
/start
  ──▶ Welcome message + Language buttons
      [English 🇬🇧]  [Hindi 🇮🇳]
  ──▶ "Language set! Choose your time:"
      [07:00 AM]  [08:00 AM]  [09:00 AM]
  ──▶ "✅ All set! You'll receive your digest at 08:00 AM."
```

---

## Scheduler

The scheduler architecture follows a **"Lazy Initialization"** model:

```
Every Hour at the top of the hour (:00)
│
├── Query DB: subscribers with delivery_time = current_hour?
│
├── YES ──▶ ensure_digest_generated()
│            ├── digest files exist? → SKIP (use cached files)
│            └── NO → run full pipeline (expensive, once/day)
│
├── Pre-generate voice notes if missing
│   ├── EN voice → digest_YYYY-MM-DD_en.mp3
│   └── HI voice → digest_YYYY-MM-DD_hi.mp3
│
└── For each subscriber:
    ├── Fetch their language from DB
    ├── Send text digest (language-matched file)
    ├── Send voice note (language-matched audio)
    └── Sleep 1 second (Telegram rate limit)
```

---

## Landing Page

**Built with**: Next.js 16 (App Router), Tailwind CSS, Framer Motion, shadcn/ui

**Sections**:
- **Hero**: Animated rotating headline words (noise → hype → scrolling → FOMO)
- **Features**: Bento-grid layout with 6 feature cards
- **How It Works**: 4-step card layout with animated zigzag connectors
- **Sample Digest**: 3D scroll animation showing a real Telegram message mockup
- **FAQ**: Accordion with 5 questions including bilingual support info
- **CTA**: Full-width indigo section with Telegram subscribe button

All "Subscribe" buttons link directly to `https://t.me/aitechdigest_bot`.

---

## Difficulties Faced & How We Solved Them

### 1. Achieving Zero-Cost Scaling
- **The Problem**: Delivering daily AI news and audio to thousands of users typically incurs massive LLM API and TTS generation costs.
- **The Solution**: 
  - Implemented **"lazy initialization"** and aggressive caching so LLM text and `edge-tts` audio generate **only once per day per language**.
  - Built a layered deduplication system (In-Session, Cross-Day DB, and Same-Day JSON Cache) to prevent wasting tokens.
  - Embedded a lightweight HTTP server in the backend, enabling the bot to run entirely on Render's Free Web Service tier.

### 2. Crafting a Readable Telegram Delivery Format
- **The Problem**: Dense AI news (with context, summaries, and impact statements) easily turns into an unreadable wall of text on mobile screens. Additionally, character limits truncated summaries and Telegram's MarkdownV2 parser easily broke.
- **The Solution**: 
  - Removed all character truncation limits and stripped distracting emojis from the body text.
  - Switched to a clean, spacious bullet-point layout with intentional line breaks between each story component (Source, Summary, Context, Impact).
  - Added dynamic escaping for all special characters to safely satisfy Telegram's MarkdownV2 constraints.

### 3. Delivering Authentic Multilingual Audio
- **The Problem**: While translating text to Hindi was straightforward, generating the voice briefing resulted in awkward "Hinglish" (the TTS model reading hardcoded English transitions like "First up..." with a thick Hindi accent).
- **The Solution**: 
  - Built a language-aware Voice Engine that uses entirely separate template dictionaries for English and Hindi.
  - Injected native Hindi intros ("सुप्रभात!"), transitions ("अगली खबर..."), and outros when Hindi is selected.
  - Ensured the final audio feels like a seamless, high-quality local broadcast.

### 4. Refining the Mobile Web Experience
- **The Problem**: The Next.js landing page suffered from critical overlap and alignment issues on small mobile screens (e.g., the "Subscribe Free" button crashing into the Dark Mode toggle, uncentered Hero buttons, and wrapping FAQ text).
- **The Solution**: 
  - Hid redundant CTA buttons in the mobile navbar, relying instead on the massive Hero CTA.
  - Forced flex containers to full width with explicit center alignments for the Hero buttons.
  - Locked the FAQ accordion components to a strict left-aligned text constraint to prevent them from inheriting parent centering rules.

### 5. Server Timezone Shifts & On-Demand Delivery
- **The Problem**: 
  - Render servers default to UTC, causing the scheduler to wake up 5.5 hours late for Indian Standard Time (IST) users.
  - Additionally, since the scheduler uses "lazy initialization" to save costs, the `/latest` command failed to retrieve today's news if there were no scheduled deliveries earlier that morning.
- **The Solution**: 
  - Configured `scheduler.py` to evaluate the current time and dates using the `ZoneInfo("Asia/Kolkata")` timezone.
  - Replaced the schedule library's startup-offset dependent loop in run.py with a direct, custom IST time-check loop. This reads time explicitly using ZoneInfo("Asia/Kolkata") and triggers hourly_job exactly at :00 IST, completely bypassing system timezone or container boot timing offsets.
  - Upgraded the `/latest` Telegram command to dynamically trigger `ensure_digest_generated()` on demand if the local text files are missing.
  - Added a hybrid MongoDB GridFS storage strategy to save generated text digests and voice notes in the database so that they are not lost during container redeployments.

---

## Setup & Installation

### Prerequisites
- Python 3.12+
- MongoDB (local or Atlas)
- Groq API Key (free tier available)
- Telegram Bot Token (from @BotFather)

### Local Setup

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/ai-news-agent.git
cd ai-news-agent

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env with your API keys

# 5. Run the full pipeline manually
python3 main.py

# 6. Send the digest to Telegram
python3 telegram_bot.py --send

# 7. Start the bot + scheduler together
python3 run.py

# 8. Start the landing page
cd landing && npm install && npm run dev
```

---

## Deployment

| Component | Platform | Command |
|---|---|---|
| Database | MongoDB Atlas (M0 Free) | Connect via Atlas URI |
| Backend Bot | Render (Web Service) | `python run.py` |
| Frontend | Vercel | Root directory: `landing/` |

### Render Configuration
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python run.py` (locked via `Procfile` so a dashboard reset can't break the boot)
- **Instance Type**: Free (Web Service)
- **Startup self-test**: On boot `run.py` pings MongoDB, validates the Telegram token, and counts active subscribers. If any check fails it aborts with a clear error instead of running a dead service.
- **Important**: We integrated a lightweight HTTP health-check server inside `run.py` so it cleanly binds to Render's `$PORT`, allowing the entire backend to run on the **Free Web Service** tier instead of requiring a paid Background Worker.
- Add all environment variables in Render's dashboard.
- *Tip*: Use a free service like [cron-job.org](https://cron-job.org/) to ping your Render URL every 10 minutes to keep the bot awake 24/7!

### Vercel Configuration
- Set **Root Directory** to `landing/` during import
- Framework auto-detected as Next.js
- No environment variables needed

---

## Environment Variables

Create a `.env` file in the project root:

```env
# Groq LLM API
GROQ_API_KEY=your_groq_api_key_here

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token_from_botfather
TELEGRAM_CHAT_ID=your_personal_chat_id

# MongoDB
MONGO_URI=mongodb://localhost:27017
# For production:
# MONGO_URI=mongodb+srv://user:***@cluster.mongodb.net/

# Admin failure alerts (optional)
# If unset, failure alerts go to the oldest subscriber so you see errors
# in Telegram without needing Render's paid-tier log history.
ADMIN_CHAT_ID=
```

---

## Project Structure

```
ai-news-agent/
│
├── 🧠 Core Pipeline
│   ├── graph.py           # LangGraph pipeline definition (4 nodes)
│   ├── fetch_news.py      # RSS/Reddit/HN ingestion, dedup, age filtering
│   ├── summarize.py       # LLM scoring, ranking, diversification
│   ├── llm.py             # Groq ChatGroq instances
│   └── thumbnail.py       # Zero-cost Pillow per-story cover images
│
├── 🤖 Automation
│   ├── main.py            # Pipeline runner + Hindi translation
│   ├── scheduler.py       # Hourly IST scheduler + lazy digest init + failure alerts
│   ├── telegram_bot.py    # Bot commands + sequential thumbnail gallery sender
│   ├── voice_engine.py    # edge-tts voice generation (EN + HI)
│   ├── db.py              # MongoDB operations
│   ├── utils.py           # Shared helpers (IST date string, MarkdownV2 escaping)
│   └── run.py             # Unified entry point (bot + scheduler + self-test)
│
├── 🌐 Frontend
│   └── landing/           # Next.js 16 landing page
│       ├── app/           # App router pages
│       └── components/    # Sections, Hero, UI components
│
├── 📁 Generated Output
│   └── digests/           # Daily digest text + audio files
│       ├── digest_YYYY-MM-DD_en.txt
│       ├── digest_YYYY-MM-DD_hi.txt
│       ├── digest_YYYY-MM-DD_en.mp3
│       └── digest_YYYY-MM-DD_hi.mp3
│
├── ⚙️ Configuration
│   ├── .env               # API keys (not committed)
│   ├── .env.example       # Template with all required vars
│   ├── Procfile           # Render start command (python run.py)
│   └── requirements.txt   # Python dependencies
```
│
└── 📖 Documentation
    └── README.md          # This file
```

---

*Built with ❤️ by Ayush Aryan — Making AI news accessible to everyone, one briefing at a time.*
