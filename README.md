# 🔥 AI Tech Digest Agent

> **Your daily 3-minute AI briefing. Read less, know more. 🎙️**
>
> A fully autonomous AI agent that fetches, ranks, summarizes, and delivers the top 5 AI tech stories of the day — as a formatted Telegram message and a human-quality voice briefing — in English or Hindi.

---

## 📋 Table of Contents

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

1. Pulls fresh articles from **11 high-signal RSS sources** (OpenAI Blog, Google AI, Meta AI, ArXiv, Hacker News, TechCrunch, and more)
2. Runs each article through an **LLM-powered scoring pipeline** — scoring innovation, impact, and credibility
3. Selects the **Top 5 stories** with category-diversity enforcement (no single topic dominates)
4. Translates the digest to **Hindi** using the same LLM
5. Generates **human-quality voice briefings** in both English (Ava Neural) and Hindi (Madhur Neural)
6. Delivers the text digest + audio to each subscriber on **Telegram** at their chosen time
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
│  11 RSS feeds   LLM scoring     Top-5 select    Format digest  │
│  Reddit API     Parallel exec   Category caps   Hindi translate │
│  Dedup checks   22hr cache      Source limits                   │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Voice Engine (edge-tts)                     │
│                                                                  │
│   EN Digest (.txt) ──▶ Ava Neural ──▶ digest_YYYY-MM-DD_en.mp3 │
│   HI Digest (.txt) ──▶ Madhur Neural ─▶ digest_YYYY-MM-DD_hi.mp3│
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Telegram Bot + Hourly Scheduler                  │
│                                                                  │
│   Scheduler wakes every hour (:00)                               │
│   ──▶ Finds subscribers for that hour                            │
│   ──▶ Generates digest if not done yet (lazy init)               │
│   ──▶ Sends text + voice in user's language                      │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     MongoDB (Two Collections)                     │
│                                                                  │
│   subscribers  → chat_id, language, delivery_time, active        │
│   history      → link, fingerprint (permanent dedup ledger)      │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| **AI Orchestration** | [LangGraph](https://github.com/langchain-ai/langgraph) | Stateful, multi-node AI pipeline |
| **LLM** | [Groq API](https://groq.com/) — `llama-3.3-70b-versatile` | Article scoring, summarization, translation |
| **RSS Parsing** | `feedparser` + `requests` | Fetching articles from 11 sources |
| **Text-to-Speech** | [edge-tts](https://github.com/rany2/edge-tts) — Microsoft Neural | Voice briefings in EN & HI |
| **Telegram** | [python-telegram-bot v22](https://python-telegram-bot.org/) | Delivery, bot commands, inline keyboards |
| **Database** | [MongoDB](https://www.mongodb.com/) + PyMongo | Subscribers + deduplication ledger |
| **Scheduling** | [schedule](https://schedule.readthedocs.io/) | Hourly job runner |
| **Frontend** | Next.js 16 + Tailwind CSS + Framer Motion | Landing page |
| **Language** | Python 3.12+ | Core backend |
| **Caching** | File-based JSON | 22-hour LLM response cache |

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
  ──▶ "✅ All set! You'll receive your digest daily at 08:00 AM"
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

### Step 3 — LangGraph Pipeline (Runs Once Per Day)

```
NODE 1: FETCH
  ├─ Pull RSS from 11 sources in parallel
  ├─ Apply age filters (lab blogs: 7 days, news: 2 days)
  ├─ Check MongoDB history (permanent dedup)
  ├─ Check title fingerprint (cross-source dedup)
  └─ Returns ~40-80 raw candidate articles

NODE 2: ANALYZE (Parallel LLM calls, 4 threads)
  ├─ Stage 0: Keyword pre-filter (zero tokens — removes deals, coupons)
  ├─ Stage 1: Check 22-hour JSON cache (skip already-scored articles)
  ├─ Stage 2: For uncached articles, call Groq LLM with structured prompt
  │   └─ Returns JSON: {keep, category, summary, context, innovation(1-5),
  │                      impact(1-5), credibility(1-5), noise(0-1), why_it_matters}
  └─ Write results back to cache

NODE 3: RANK
  ├─ Compute total_score = (innovation + impact + credibility - noise*10) * source_weight
  ├─ Apply category caps: max 2 AI, 2 big_tech, 2 startup, 1 research, 1 infra
  ├─ Apply source cap: max 2 articles per source
  ├─ ArXiv and Reddit get -10% to -20% score penalty (papers rarely matter same day)
  └─ 3-pass fallback fill to always reach exactly 5 stories

NODE 4: OUTPUT
  ├─ Format English digest with emoji markers (🔥/⚡, 📰, 🧠, 👉, 🔗)
  ├─ Translate to Hindi via LLM (preserves emojis, company names, formatting)
  └─ Save both as digest_YYYY-MM-DD_en.txt and digest_YYYY-MM-DD_hi.txt
```

---

## Module Breakdown

### `graph.py` — The Orchestrator
Defines the LangGraph `StateGraph` with a shared `State` TypedDict that flows through all 4 nodes. Each node reads from and writes to this shared state, keeping the pipeline clean and testable in isolation.

### `fetch_news.py` — The Ingestion Layer
- **11 RSS Sources** with per-source credibility weights (1.2x–1.8x) and daily caps
- **Reddit Integration** via the JSON API, filtering posts by minimum upvote score (80+)
- **Title Fingerprinting**: Strips stopwords, takes first 6 meaningful words to create a semantic key — catches the same story published on multiple outlets
- **Age Filtering**: Lab blogs allowed up to 7 days old; news sites capped at 2 days

### `summarize.py` — The Intelligence Layer
- **Single LLM prompt per article** — scoring + summarization + categorization in one call (minimizes token usage on Groq free tier)
- **Parallel processing** via `ThreadPoolExecutor(max_workers=4)` — 4x faster than sequential
- **`rank_and_diversify()`**: Three-pass selection ensuring the daily digest is never dominated by a single topic or source

### `cache.py` — The Cost Shield
A simple JSON file cache with a 22-hour TTL. Stores both kept and rejected articles (rejected are stored as `{}` sentinel values). This prevents re-spending tokens on articles already evaluated. Capped at 500 entries with auto-eviction.

### `db.py` — The Database Layer
Two MongoDB collections:
- **`subscribers`**: Stores `chat_id`, `username`, `language`, `delivery_time`, `active` flag
- **`history`**: Permanent ledger — every sent article's URL and title fingerprint are stored here forever. Never expires.

### `voice_engine.py` — The Audio Layer
- **Language-aware script builder**: Generates fully localized scripts — Hindi scripts use native Hindi intros (`सुप्रभात...`), transitions (`अगली खबर...`), and outros
- **`_clean_for_speech()`**: Strips URLs, emojis, category labels, markdown syntax, and score tags that sound awkward when read aloud
- **Threading safety**: Uses `threading.Thread` to run `asyncio.run()` safely if called from within an existing event loop (avoids `RuntimeError: no running event loop`)

### `telegram_bot.py` — The Delivery Layer
- **Two modes**: `--send` (broadcast) and `--bot` (interactive registration)
- **Emoji-based parser**: Parses digest files using Unicode emoji codepoints (`📰`, `🧠`, `👉`) instead of English strings — ensures both EN and HI digests are parsed correctly
- **MarkdownV2 escaping**: All dynamic text is escaped before sending via Telegram's strict MarkdownV2 parser
- **Guard clauses**: All handlers check for `None` on `update.message`, `update.effective_user`, etc.

### `scheduler.py` — The Background Worker
- Runs an hourly loop using the `schedule` library
- **Lazy Initialization**: Only runs the expensive pipeline if the digest files don't yet exist for today
- **7-day cleanup**: Automatically deletes digest and audio files older than 7 days to prevent disk exhaustion

### `run.py` — The Unified Entry Point
Runs the Telegram Bot (main thread) + Scheduler (daemon thread) in one process for single-server cloud deployment.

---

## Deduplication System

The system uses a **layered, three-level deduplication strategy**:

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

Level 3 — LLM Cache (Within Same Day)
  Tool: File-based JSON cache with 22-hour TTL
  Scope: Multiple runs within the same day
  Example: If main.py runs twice in one day, avoids double LLM spend
```

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
Every Hour at :00
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

### 1. The "Hinglish" Voice Bug
**Problem**: The Hindi voice briefing was using English transitions ("First up...", "Why it matters...", "A bit of background..."). Since these were baked into the script builder as hardcoded English strings, the TTS model read English phrases in a Hindi accent — producing awkward "Hinglish" audio.

**Root Cause**: `build_script_from_articles()` in `voice_engine.py` had no language awareness. It used one set of templates for all languages.

**Solution**: Refactored the script builder to accept a `lang` parameter. Added a complete set of native Hindi intro phrases, story transitions, background transitions, and outros. The function now picks the correct template set before assembling the script.

---

### 2. Critical Indentation Errors in `fetch_news.py`
**Problem**: The pipeline would crash immediately on startup with `IndentationError`. The file had a mixture of tabs and spaces from multiple editing sessions, causing Python's parser to fail on nested `try/except` blocks inside `for` loops.

**Solution**: Complete rewrite of `fetch_news.py` from scratch with consistent 4-space indentation. Added explicit `try/except` blocks around every individual RSS source fetch, so a single failed network request no longer crashes the entire ingestion run.

---

### 3. Scheduler Crash on LLM Timeout
**Problem**: If the Groq API was slow or returned a rate-limit error during the `analyze_node`, the exception would bubble all the way up to the scheduler's `hourly_job()` function and crash the loop — meaning no future deliveries would happen.

**Solution**: Wrapped `run_pipeline()` call in `ensure_digest_generated()` with a top-level `try/except`. Added inner `try/except` blocks in `analyze_articles_parallel()` per article. A single failing article is skipped rather than killing the batch.

---

### 4. Delivery Time Callback Bug
**Problem**: When a user tapped "07:00 AM" on the Telegram inline keyboard, the callback data was `"time_07:00 AM"`. The handler used `data.split("_")[1]` which returned `"07:00 AM"` ✅. However the scheduler formatted the time as `datetime.now().strftime("%I:00 %p")` which produces `"07:00 AM"` ✅. The bug was a subtle case sensitivity issue — `strftime` on some systems returns `"07:00 am"` (lowercase). The DB stored `"07:00 AM"` but the query used the system-formatted string.

**Solution**: Normalized both sides to uppercase with `.upper()` when comparing, and switched the callback data parser from fragile `split("_")[1]` to a safe prefix strip: `data[len("time_"):]`.

---

### 5. New Subscribers Never Receiving News
**Problem**: A user who opened the bot but closed Telegram after choosing their language (but before choosing a delivery time) had no `delivery_time` field in their MongoDB document. The `get_subscribers_by_time()` query filters by `delivery_time`, so this user was permanently invisible to the scheduler and would never receive anything — silently.

**Solution**: Added `$setOnInsert` to the `save_subscriber()` upsert call in `db.py`. This sets default values (`language: "en"`, `delivery_time: "08:00 AM"`) only when the document is first created, never overwriting existing preferences. This ensures every new subscriber has a valid delivery time even if they abandon the registration flow.

---

### 6. IDE False-Positive Import Errors
**Problem**: VS Code's Pylance/Pyrefly linter showed red squiggles on `import edge_tts` and `import telegram` even though both packages were installed in the project's `./venv/`. The IDE was using the global Python interpreter at `/Library/Frameworks/Python.framework/Versions/3.14/` instead of the local virtual environment.

**Solution (Two-Stage)**:
1. Added a `.vscode/settings.json` with explicit absolute paths to the venv interpreter and site-packages.
2. Created `pyrightconfig.json` in the project root pointing `venvPath` to `.` and `venv` to `"venv"`. Pyright reads this file automatically and correctly resolves all imports.
3. Final fallback: Installed the packages globally (`pip3 install python-telegram-bot edge-tts`) so even the global interpreter could resolve them.

---

### 7. Voice Engine CLI Looking for Wrong Filename
**Problem**: Running `python3 voice_engine.py` from the command line would always fail with `❌ Digest file not found`. The CLI code hardcoded the digest filename as `digest_YYYY-MM-DD.txt` but all files are actually saved as `digest_YYYY-MM-DD_en.txt` (with the `_en` language suffix).

**Solution**: Updated the CLI's default filename pattern to `digest_YYYY-MM-DD_en.txt`.

---

### 8. `--voice` CLI Argument Rejecting Hindi
**Problem**: The `--voice` argument in the voice engine CLI used `choices=list(VOICE_OPTIONS.keys())`, which only allowed short keys like `"ava"`, `"sonia"`. This meant passing `--voice hi-IN-MadhurNeural` would throw an `argparse` error.

**Solution**: Removed the `choices=` constraint entirely. The underlying `VOICE_OPTIONS.get(voice_key, voice_key)` logic already handles unknown keys by treating them as direct `edge-tts` voice names — so any valid Microsoft Neural voice name is now accepted.

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
| Backend Bot | Render (Background Worker) | `python run.py` |
| Frontend | Vercel | Root directory: `landing/` |

### Render Configuration
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `python run.py`
- **Instance Type**: Free (Background Worker)
- Add all 3 environment variables in Render's dashboard

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
# MONGO_URI=mongodb+srv://user:password@cluster.mongodb.net/
```

---

## Project Structure

```
ai-news-agent/
│
├── 🧠 Core Pipeline
│   ├── graph.py           # LangGraph pipeline definition (4 nodes)
│   ├── fetch_news.py      # RSS ingestion, dedup, age filtering
│   ├── summarize.py       # LLM scoring, ranking, diversification
│   ├── cache.py           # File-based 22-hour LLM response cache
│   └── llm.py             # Groq ChatGroq instances
│
├── 🤖 Automation
│   ├── main.py            # Pipeline runner + Hindi translation
│   ├── scheduler.py       # Hourly scheduler + lazy digest init
│   ├── telegram_bot.py    # Bot commands + broadcast sender
│   ├── voice_engine.py    # edge-tts voice generation (EN + HI)
│   ├── db.py              # MongoDB operations
│   └── run.py             # Unified entry point (bot + scheduler)
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
│   ├── requirements.txt   # Python dependencies
│   ├── pyrightconfig.json # IDE type checker config
│   └── .vscode/           # VS Code interpreter settings
│
└── 📖 Documentation
    └── README.md          # This file
```

---

## License

MIT License — Free to use, fork, and build upon.

---

*Built with ❤️ by Ayush Aryan — Making AI news accessible to everyone, one briefing at a time.*
