# fetch_news.py

import feedparser
import requests
import hashlib
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TechDigestBot/1.0)"}


def _http_get(url: str, timeout: int = 12, retries: int = 4, backoff: float = 3.0):
    """GET with exponential backoff. Absorbs transient 429/5xx/SSL blips
    (Reddit and hnrss.org are prone to rate-limiting). Returns a response-like
    object with status_code=0 on total failure so callers skip gracefully."""
    for attempt in range(retries):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            if resp.status_code == 429 and attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"  ⏳ 429 rate-limited — retry in {wait:.0f}s ({attempt+1}/{retries})")
                time.sleep(wait)
                continue
            return resp
        except Exception as exc:
            if attempt < retries - 1:
                wait = backoff * (2 ** attempt)
                print(f"  ⏳ request error ({exc}) — retry in {wait:.0f}s")
                time.sleep(wait)
    class _Empty:
        status_code = 0
        content = b""
        text = ""
        def json(self):
            return {}
    return _Empty()

# Age limits by source tier.
MAX_AGE_BY_SOURCE = {
    "OpenAI Blog":        7,
    "Google AI Blog":     7,
    "Microsoft AI Blog":  7,
    "Meta AI Engineering":7,
    "Anthropic Blog":     7,
    "Google DeepMind":    5,
    "MIT Tech Review AI": 4,
    "The Verge AI":       2,
    "Wired AI":           2,
    "VentureBeat AI":     2,
    "TechCrunch AI":      2,
    "Ars Technica":       2,
    "ArXiv ML":           2,
    "Hacker News AI":     1,
}
MAX_ARTICLE_AGE_DEFAULT = 3


# ─────────────────────────────────────────────────────────────────────────────
# SOURCE REGISTRY
# ─────────────────────────────────────────────────────────────────────────────

RSS_SOURCES = [
    {
        "url":    "https://openai.com/blog/rss.xml",
        "name":   "OpenAI Blog",
        "weight": 1.8,
        "cap":    5,
    },
    {
        "url":    "https://blog.google/technology/ai/rss/",
        "name":   "Google AI Blog",
        "weight": 1.7,
        "cap":    5,
    },
    {
        # blogs.microsoft.com/ai/feed/ now returns HTTP 410 Gone.
        # Microsoft Research publishes a working RSS at this URL.
        "url":    "https://www.microsoft.com/en-us/research/feed/",
        "name":   "Microsoft AI Blog",
        "weight": 1.6,
        "cap":    5,
    },
    {
        "url":    "https://engineering.fb.com/category/ai-research/feed/",
        "name":   "Meta AI Engineering",
        "weight": 1.6,
        "cap":    5,
    },
    {
        # Anthropic has no official RSS; this is a community-maintained mirror
        # (Olshansk/rss-feeds) that tracks anthropic.com/news. Can go stale if the
        # upstream repo stops updating — treat as best-effort.
        "url":    "https://raw.githubusercontent.com/Olshansk/rss-feeds/main/feeds/feed_anthropic_news.xml",
        "name":   "Anthropic Blog",
        "weight": 1.7,
        "cap":    5,
    },
    {
        "url":    "https://deepmind.google/blog/feed/",
        "name":   "Google DeepMind",
        "weight": 1.6,
        "cap":    5,
    },
    {
        "url":    "https://www.technologyreview.com/topic/artificial-intelligence/feed",
        "name":   "MIT Tech Review AI",
        "weight": 1.3,
        "cap":    6,
    },
    {
        # The Verge's AI-specific RSS path (.../ai-artificial-intelligence/rss/index.xml)
        # now 404s. The main Verge RSS is still live and AI-heavy enough for our audience.
        "url":    "https://www.theverge.com/rss/index.xml",
        "name":   "The Verge AI",
        "weight": 1.4,
        "cap":    8,
    },
    {
        "url":    "https://www.wired.com/feed/tag/ai/latest/rss",
        "name":   "Wired AI",
        "weight": 1.4,
        "cap":    8,
    },
    {
        "url":    "https://techcrunch.com/category/artificial-intelligence/feed/",
        "name":   "TechCrunch AI",
        "weight": 1.3,
        "cap":    8,
    },
    {
        "url":    "https://venturebeat.com/category/ai/feed/",
        "name":   "VentureBeat AI",
        "weight": 1.2,
        "cap":    8,
    },
    {
        "url":    "https://arstechnica.com/gadgets/feed/",
        "name":   "Ars Technica",
        "weight": 1.2,
        "cap":    6,
    },
    {
        "url":    "https://arxiv.org/rss/cs.LG",
        "name":   "ArXiv ML",
        "weight": 1.4,
        "cap":    3,
    },
]

# Reddit: use the subreddit .rss Atom feed (NO OAuth needed). The .json endpoint
# is blocked (HTTP 403) for bot user-agents; .rss works with a browser-like UA.
REDDIT_SOURCES = [
    {
        "subreddit": "MachineLearning",
        "name":      "r/MachineLearning",
        "weight":    1.3,
        "min_score": 80,
        "cap":       4,
        "kind":      "reddit_rss",
    },
]

# Hacker News via the Algolia search API (no RSS host dependency;
# hnrss.org is frequently down / SSL-flaky). No auth required.
HN_SOURCES = [
    {
        "url":    "https://hn.algolia.com/api/v1/search?query=AI%20OR%20LLM%20OR%20GPT%20OR%20Claude%20OR%20Gemini&tags=story&hitsPerPage=20",
        "name":   "Hacker News AI",
        "weight": 1.3,
        "cap":    3,
        "kind":   "hn_algolia",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _article_id(title: str, link: str) -> str:
    return hashlib.md5(f"{title}{link}".encode()).hexdigest()


def _title_fingerprint(title: str) -> str:
    import re, html
    t = html.unescape(title).lower()
    t = re.sub(r"[^a-z0-9 ]", " ", t)
    stop = {"the","a","an","and","or","to","in","of","for","on","at","is","it",
            "this","that","with","how","why","what","its","are","was","has","by"}
    words = [w for w in t.split() if w and w not in stop]
    return " ".join(words[:6])


def _parse_publish_date(entry: dict) -> datetime | None:
    parsed = entry.get("published_parsed") or entry.get("updated_parsed")
    if parsed:
        try:
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except Exception:
            return None
    return None


def _is_too_old(entry: dict, max_days: int) -> bool:
    pub_date = _parse_publish_date(entry)
    if not pub_date:
        return False
    now = datetime.now(timezone.utc)
    return (now - pub_date) > timedelta(days=max_days)


def _format_age(entry: dict) -> str:
    pub_date = _parse_publish_date(entry)
    if not pub_date:
        return "recently"
    delta = datetime.now(timezone.utc) - pub_date
    if delta.days > 0:
        return f"{delta.days}d ago"
    hours = int(delta.total_seconds() / 3600)
    if hours < 24:
        return f"{hours}h ago"
    return f"{delta.days}d ago"


# ─────────────────────────────────────────────────────────────────────────────
# RSS FETCHER
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_rss_source(source: dict, seen_ids: set, seen_fps: set) -> list[dict]:
    cap = source.get("cap", 6)
    try:
        response = _http_get(source["url"])
        if response.status_code != 200:
            print(f"  ⚠️  HTTP {response.status_code} — skipping")
            return []

        feed = feedparser.parse(response.content)
        if not feed.entries:
            print(f"  ⚠️  No entries found — skipping")
            return []

        articles = []
        skipped_old = 0

        for entry in feed.entries:
            if len(articles) >= cap:
                break

            age_limit = MAX_AGE_BY_SOURCE.get(source["name"], MAX_ARTICLE_AGE_DEFAULT)
            if _is_too_old(entry, age_limit):
                skipped_old += 1
                continue

            import html as _html
            entry_title = entry.get("title", "")
            if not isinstance(entry_title, str):
                entry_title = str(entry_title) if entry_title is not None else ""
            title = _html.unescape(entry_title).strip()

            entry_link = entry.get("link", "")
            if not isinstance(entry_link, str):
                entry_link = str(entry_link) if entry_link is not None else ""
            link = entry_link.strip()

            if not title or not link:
                continue

            uid = _article_id(title, link)
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            fp = _title_fingerprint(title)
            try:
                from db import is_article_sent
                if is_article_sent(link, fp):
                    print(f"  🔁 ALREADY SENT skipped: {title[:55]}")
                    continue
            except Exception:
                pass

            if fp in seen_fps:
                print(f"  🔁 NEAR-DUP skipped: {title[:55]}")
                continue
            seen_fps.add(fp)

            content_val = ""
            entry_content = entry.get("content")
            if isinstance(entry_content, list) and len(entry_content) > 0:
                first_content = entry_content[0]
                if isinstance(first_content, dict):
                    content_val = first_content.get("value", "")
            if not content_val:
                summary_val = entry.get("summary", "")
                if isinstance(summary_val, str):
                    content_val = summary_val
                elif summary_val is not None:
                    content_val = str(summary_val)
            if not isinstance(content_val, str):
                content_val = str(content_val) if content_val is not None else ""
            content = content_val.strip()

            age_str = _format_age(entry)

            articles.append({
                "id":            uid,
                "title":         title,
                "link":          link,
                "summary":       content[:1000],
                "source":        source["name"],
                "source_weight": source["weight"],
                "published":     entry.get("published", ""),
                "age":           age_str,
            })

        if skipped_old:
            print(f"  ⏰ Skipped {skipped_old} stale articles")

        return articles

    except Exception as e:
        print(f"  ❌  Failed to fetch {source['url']}: {e}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# REDDIT FETCHER
# ─────────────────────────────────────────────────────────────────────────────

def _fetch_reddit_source(source: dict, seen_ids: set, seen_fps: set) -> list[dict]:
    # Use the subreddit .rss Atom feed — NO OAuth required.
    # (The .json endpoint is blocked with HTTP 403 for bot user-agents.)
    url = f"https://www.reddit.com/r/{source['subreddit']}/.rss"
    try:
        response = _http_get(url)
        if response.status_code != 200:
            print(f"  ⚠️  HTTP {response.status_code} — skipping")
            return []

        feed = feedparser.parse(response.content)
        if not feed.entries:
            print(f"  ⚠️  No entries found — skipping")
            return []

        articles = []
        for entry in feed.entries:
            if len(articles) >= source["cap"]:
                break

            # Reddit Atom entries nest the real post URL under <link href=...>
            link = entry.get("link", "")
            if isinstance(link, dict):
                link = link.get("href", "")
            title = entry.get("title", "").strip()
            if not title or not link:
                continue

            uid = _article_id(title, link)
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            fp = _title_fingerprint(title)
            try:
                from db import is_article_sent
                if is_article_sent(link, fp):
                    print(f"  🔁 ALREADY SENT skipped: {title[:55]}")
                    continue
            except Exception:
                pass

            if fp in seen_fps:
                print(f"  🔁 NEAR-DUP skipped: {title[:55]}")
                continue
            seen_fps.add(fp)

            # Score is not in the .rss feed; approximate by applying min_score gate
            # only when we can read it from the summary text (rare). Default: keep.
            content = entry.get("summary", "") or title

            articles.append({
                "id":            uid,
                "title":         title,
                "link":          link,
                "summary":       content[:1000],
                "source":        source["name"],
                "source_weight": source["weight"],
                "published":     entry.get("published", ""),
                "age":           "today",
                "upvotes":       None,
            })

        return articles

    except Exception as exc:
        print(f"  ❌ Reddit error: {exc}")
        return []


def _fetch_hn_algolia(source: dict, seen_ids: set, seen_fps: set) -> list[dict]:
    """Fetch Hacker News top AI/LLM stories via the Algolia search API.
    Avoids the flaky hnrss.org RSS host. No auth required."""
    try:
        response = _http_get(source["url"])
        if response.status_code != 200:
            print(f"  ⚠️  HTTP {response.status_code} — skipping")
            return []
        hits = response.json().get("hits", [])
        if not hits:
            print(f"  ⚠️  No hits — skipping")
            return []

        articles = []
        for hit in hits:
            if len(articles) >= source["cap"]:
                break
            title = (hit.get("title") or hit.get("story_title") or "").strip()
            link = hit.get("url") or hit.get("story_url") or ""
            if not title:
                continue
            # Fall back to the HN discussion page if there's no outbound link
            if not link:
                link = f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
            points = hit.get("points") or 0

            uid = _article_id(title, link)
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            fp = _title_fingerprint(title)
            try:
                from db import is_article_sent
                if is_article_sent(link, fp):
                    print(f"  🔁 ALREADY SENT skipped: {title[:55]}")
                    continue
            except Exception:
                pass

            if fp in seen_fps:
                print(f"  🔁 NEAR-DUP skipped: {title[:55]}")
                continue
            seen_fps.add(fp)

            articles.append({
                "id":            uid,
                "title":         title,
                "link":          link,
                "summary":       (hit.get("story_text") or "")[:1000],
                "source":        source["name"],
                "source_weight": source["weight"],
                "published":     hit.get("created_at", ""),
                "age":           "today",
                "upvotes":       points,
            })

        return articles

    except Exception as exc:
        print(f"  ❌ HN Algolia error: {exc}")
        return []


# ─────────────────────────────────────────────────────────────────────────────
# MAIN FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_news() -> list[dict]:
    all_articles:   list[dict] = []
    seen_ids:       set[str]   = set()
    seen_fingerprints: set[str] = set()

    for source in RSS_SOURCES:
        print(f"📡 Fetching: {source['name']}")
        articles = _fetch_rss_source(source, seen_ids, seen_fingerprints)
        all_articles.extend(articles)
        status = f"✅ {len(articles)} articles" if articles else "⚠️  0 articles (all filtered or failed)"
        print(f"  {status}")

    for source in REDDIT_SOURCES:
        kind = source.get("kind", "reddit_rss")
        fetcher = _fetch_reddit_source if kind == "reddit_rss" else _fetch_rss_source
        print(f"📡 Fetching: {source['name']} ({kind})")
        articles = fetcher(source, seen_ids, seen_fingerprints)
        all_articles.extend(articles)
        if articles:
            print(f"  ✅ {len(articles)} articles added")

    for source in HN_SOURCES:
        print(f"📡 Fetching: {source['name']} ({source.get('kind', 'hn_algolia')})")
        articles = _fetch_hn_algolia(source, seen_ids, seen_fingerprints)
        all_articles.extend(articles)
        if articles:
            print(f"  ✅ {len(articles)} articles added")

    print(f"\n📦 Total unique articles fetched: {len(all_articles)}")
    return all_articles