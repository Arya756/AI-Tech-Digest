# AI Tech Digest Agent — System Overview

Welcome! This document provides a complete technical blueprint and flow analysis of the **AI Tech Digest Agent** project. It is designed to give you (or another assistant/developer) a comprehensive understanding of the system's architecture, database layout, component flows, and recent optimizations.

---

## 1. High-Level Concept & Value Proposition

**AI Tech Digest** is a production-grade, autonomous news agent. Twice a day (AM and PM IST), it fetches artificial intelligence and machine learning news, scores them based on high-signal criteria, selects the top 5 unique stories, generates a highly readable text summary plus a natural voice briefing (in English and Hindi), and delivers them directly to subscribers via a Telegram bot.

### Key Performance Targets:
1. **Zero-Cost Scaling**: Minimizes LLM token consumption and text-to-speech costs by using aggressive caching, in-memory checks, and **lazy initialization** (running the pipeline exactly once per day per language).
2. **Category Diversity**: Ensures the digest covers a variety of domains (research, tools, big tech, hardware, startups) rather than repeating the same major headline 5 times.
3. **No Repeats**: A multi-layered deduplication ledger guarantees that a subscriber is never sent the same story twice, even if the URL or title shifts slightly across different publishers.

---

## 2. System Architecture

The project consists of a **Python Backend Service** (handling fetching, LangGraph orchestration, DB persistence, audio generation, and Telegram communication) and a **Next.js Frontend** (the marketing landing page).

```
                      +-----------------------------------------+
                      |         Next.js Landing Page            |
                      |   (Vercel: app/page.tsx, components/)   |
                      +-----------------------------------------+
                                           |
                                           | Clicks "Subscribe Free"
                                           v
+---------------------------------------------------------------------------------+
|                                 TELEGRAM BOT                                    |
|              (Render Web Service: run.py -> telegram_bot.py)                    |
+---------------------------------------------------------------------------------+
       |                                                                  ^
       | User Prefs                                                       | Delivers
       | & Commands                                                       | Texts + Audio
       v                                                                  |
+----------------------+     Runs Every Hour IST      +---------------------------+
|   MongoDB Database   | <--------------------------- |    Scheduler Loop         |
|  (subscribers, history,|                            |    (scheduler.py)         |
|  daily_digests,      |                              +---------------------------+
|  digest_audio GridFS)|                                          |
+----------------------+                                          | If digest missing
                                                                  v
                                                      +---------------------------+
                                                      |    LangGraph Pipeline     |
                                                      |   (graph.py, main.py)     |
                                                      +---------------------------+
```

### Technical Stack
* **AI Orchestration**: LangGraph (StateGraph) for managing multi-stage pipeline flow.
* **LLM Layer**: Groq API (`llama-3.3-70b-versatile` or similar models) for scoring, summarization, and translation.
* **Database**: MongoDB (Atlas) for storing subscriber records, historical URLs, and GridFS binary audio storage.
* **TTS (Text-to-Speech)**: `edge-tts` (Microsoft Neural voices: `en-US-AvaNeural` for English and `hi-IN-MadhurNeural` for Hindi).
* **Delivery**: `python-telegram-bot v22`.
* **Frontend**: Next.js 16 (App Router), Tailwind CSS, Framer Motion, shadcn/ui.
* **Hosting**: Render (Web Service for Python backend, using a dummy HTTP port binder to satisfy the Render Free tier), Vercel (for frontend).

---

## 3. Database Schema & Collections

The database `ai_news_agent` uses four main collections:

### A. `subscribers`
Tracks active users, their communication language, and delivery timezone offsets.
```json
{
  "_id": "ObjectId(...)",
  "chat_id": "123456789",          // String - Telegram user chat ID (unique identifier)
  "username": "ayusharyan",         // String - Telegram username (nullable)
  "active": true,                  // Boolean - Flag for active/unsubscribed users
  "language": "en",                // String - "en" or "hi"
  "delivery_time": "08:00 AM"      // String - "07:00 AM" / "08:00 AM" / "09:00 AM"
}
```

### B. `history`
A permanent deduplication ledger that keeps track of every story ever broadcasted.
```json
{
  "_id": "ObjectId(...)",
  "link": "https://example.com/ai-news",  // String - Raw article URL
  "fingerprint": "cursor ai launches agent" // String - 6-word semantic title fingerprint
}
```

### C. `daily_digests`
Stores the generated raw text digest so it can be loaded instantly for late-subscribers or `/latest` requests without re-running the LLM pipeline.
```json
{
  "_id": "ObjectId(...)",
  "date_str": "2026-06-03_AM",     // String - YYYY-MM-DD_AM or YYYY-MM-DD_PM
  "lang": "en",                    // String - "en" or "hi"
  "content": "Formatted digest...",// String - Raw text digest markdown
  "created_at": 1780492800.0       // Float - Epoch timestamp
}
```

### D. `digest_audio` (GridFS)
GridFS storage collection containing binary `.mp3` briefings, preventing disk-exhaustion issues on server restarts/redeploys.
* **`digest_audio.files`**: Metadata records (`filename`, `created_at`, `length`).
* **`digest_audio.chunks`**: Binary data payloads.

---

## 4. End-to-End Workflows

### A. Subscriber Onboarding Flow
1. User clicks **Subscribe Free** on the Next.js landing page.
2. Directs to Telegram: `/start` command initiates `telegram_bot.py`.
3. The user record is saved to the `subscribers` collection (defaulting to English and `08:00 AM`).
4. Inline keyboards prompt the user to choose their preferred **Language** (`English 🇬🇧` or `Hindi 🇮🇳`) and **Delivery Time** (`07:00 AM`, `08:00 AM`, `09:00 AM`).
5. DB preferences are updated. The user is now queued for delivery.

### B. Scheduler Activation (Every Hour)
The application entry point `run.py` spins up an **IST-aware background thread** checking every 20 seconds. At the top of every hour (e.g. `08:00 AM IST` / `08:00 PM IST`):
1. **Fetch Batch**: Query MongoDB for subscribers matching the current hour (e.g., `08:00 AM` or `08:00 PM`).
2. **Lazy Initialization**: If subscribers exist but today's files do not exist in the DB:
   * Run the full LangGraph pipeline to generate English text (`main.py`).
   * Translate the output to Hindi using Groq (`llm_final`).
   * Store both English and Hindi text in the `daily_digests` collection.
3. **Pre-generate Audio**:
   * Use `voice_engine.py` to convert the text digests into English (`AvaNeural`) and Hindi (`MadhurNeural`) `.mp3` briefings.
   * Upload binary payload to GridFS and store files locally in `digests/`.
4. **Broadcast**:
   * Send the text digest and matching audio briefing to each subscriber in the batch.
   * Pause for `1 second` between messages to comply with Telegram's API rate limits.

---

## 5. LangGraph Pipeline (The Ingestion & scoring workflow)

The orchestration in `graph.py` consists of 4 nodes:

```
[fetch_node] ──> [analyze_node] ──> [rank_node] ──> [output_node]
```

### 1. `fetch_node` (Ingestion)
* Pulls articles in parallel from **12 RSS sources** (such as OpenAI, Google AI, Microsoft AI, Meta, VentureBeat, TechCrunch, ArXiv, and Hacker News) — **13 feeds total** including r/MachineLearning via the Reddit JSON API.
* Pulls trending posts from **r/MachineLearning** (Reddit JSON API) with upvotes `>= 80`.
* Applies **Age Filters**: Capping news articles to a maximum of 2 days and lab blogs to 7 days.
* Applies **Deduplication Level 1 & 2**: Immediately filters out URLs and title fingerprints matching the DB `history` collection.

### 2. `analyze_node` (Keyword Pre-filter + Parallel Scoring)
* **Stage 0 (Zero-Cost Keyword Filtering)**: Quickly rejects articles with marketing keywords (e.g., *deals, coupons, discounts, sales, shop, webinar, register for*) without hitting the LLM.
* **Stage 1 (Cache Verification)**: Checks the local `.digest_cache.json` (22-hour TTL). If the article was already processed:
  * If approved: Retrieve structured scores.
  * If rejected: Skip article (stored as `{}` sentinel).
* **Stage 2 (Groq scoring)**: For uncached articles, calls Groq LLM in parallel (3 threads) to score the story and return a structured JSON response:
  ```json
  {
    "keep": true,
    "category": "ai_tools",
    "summary": "Short 2-sentence summary...",
    "context": "Background context...",
    "why_it_matters": "Business/impact context...",
    "innovation": 4,   // 1 to 5
    "impact": 5,       // 1 to 5
    "credibility": 4,  // 1 to 5
    "noise": 0         // 0 or 1
  }
  ```

### 3. `rank_node` (Diversity Scoring & Selection)
* **Formula**:
  $$\text{Total Score} = (\text{innovation} + \text{impact} + \text{credibility} + \text{noise}) \times \text{source\_weight}$$  \quad(\text{noise is already on a } -5\dots0 \text{ scale, so it subtracts from the total})
  * A -10% to -20% score penalty is applied to Academic Papers (ArXiv) and Social Media (Reddit) since they rarely warrant top-billing on the day of publication.
* **Diversity Caps** (`CATEGORY_SLOTS` in `summarize.py`): AI:3, ai_tools:2, research:2, big_tech:2, hardware:1, startup:1, other:1, and max 2 stories per source.
* **Selection Process**: Runs a 3-pass loop to select exactly 5 articles while enforcing the above diversity constraints. If constraints cannot be met, it gracefully relaxes them.

### 4. `output_node` (Formatting & Translation)
* Formats the final 5 articles into a markdown-styled text digest block with standard unicode markers:
  * `📰` Title
  * `🏷️` Category & Source
  * `👥` Target Audience
  * `📝` Summary
  * `🧠` Context
  * `👉` Why it Matters
  * `🔗` Source Link
* The result is written to `digests/digest_YYYY-MM-DD_AM/PM_en.txt`.
* If a translation is requested, `main.py` sends the digest to Groq to produce the corresponding Hindi version, preserving tags and proper nouns.

---

## 6. Audio Generation (Voice Engine)

The voice engine (`voice_engine.py`) builds and generates natural audio files:

1. **Text Stripping**: The voice note shouldn't contain links, emojis, raw score tags, or bracketed priorities. `_clean_for_speech()` strips these out.
2. **Localization Templates**: English and Hindi use native introductory scripts and transition blocks:
   * **English**: `"Good morning/evening... Here is story number one..."`
   * **Hindi**: `"सुप्रभात/शुभ संध्या! एआई टेक डाइजेस्ट में आपका स्वागत है... पहली खबर..."`
3. **Microsoft edge-tts Engine**: Uses python `edge-tts` to request neural audio streams and saves them to `.mp3` files.
4. **GridFS Backup**: The binary file is saved in MongoDB GridFS, ensuring that if a server container restarts, the file is immediately synced back.

---

## 7. Critical Design Optimizations (Recent Updates)

Here are the key iterations and fine-tunings made to the backend codebase to improve content quality and reliability:

### A. Audience Tagging (Zero LLM cost)
Instead of asking the LLM to generate target audiences for every article, a static mapping `AUDIENCE_TAGS` translates the article category directly to the target demographic in `summarize.py`:
* `AI` / `big_tech` / `other` $\rightarrow$ `🌐 Everyone`
* `ai_tools` $\rightarrow$ `👩‍💻 Developers`
* `hardware` $\rightarrow$ `⚙️  Engineers`
* `startup` $\rightarrow$ `🚀 Founders & Investors`
* `research` $\rightarrow$ `🔬 Researchers`

### B. Explainers & Context Skip List
To stop the LLM from generating repetitive and condescending background context for popular technologies (e.g., explaining what OpenAI, Google, ChatGPT, GPUs, or AGI are every single day), the summarization prompt contains a strict **Context Skip List**:
```
CONTEXT SKIP LIST (DO NOT explain these concepts under 'context'):
- OpenAI, ChatGPT, GPT-4, GPT-5
- Google, Gemini
- Meta, Llama
- GPU, Nvidia, TSMC
- AGI (Artificial General Intelligence)
```

### C. Funding Threshold Filter
Small startup funding rounds ($1M - $10M) create excessive noise. A strict rule was established in the summarization prompt:
* Ignore startup funding rounds unless they are **>$20M** for AI startups, or **>$100M** for general technology companies.

### D. Parser Resilience & Fallback Guards
The Telegram formatter (`telegram_bot.py`) reads the generated `.txt` digest file and parses it line-by-line using unicode emojis. If a minor formatting change occurred (e.g., the `👥` emoji was missing), the tag was previously dropped silently.
* Added a **Fallback Guard**: If the audience tag is not parsed, it defaults to `"🌐 Everyone"`.
* Added **Warning Logs**: Triggers a console warning pointing out which story title missed the audience tag, ensuring that format drifts are immediately visible to developers.

---

## 8. Development & Local Execution

### Local Ingestion & Test
1. Set up a virtual environment and configure your `.env` (contains `GROQ_API_KEY`, `TELEGRAM_BOT_TOKEN`, `MONGO_URI`).
2. Run the pipeline locally to fetch and score fresh news:
   ```bash
   python3 main.py
   ```
3. To bypass the LLM cache and re-evaluate articles with fresh prompt instructions, add the refresh flag:
   ```bash
   python3 main.py --refresh
   ```
4. Start both the interactive Telegram bot daemon and the IST hourly scheduler thread:
   ```bash
   python3 run.py
   ```
