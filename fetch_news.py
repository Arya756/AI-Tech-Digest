# fetch_news.py

import feedparser
import requests
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; TechDigestBot/1.0)"}

# Age limits by source tier.
MAX_AGE_BY_SOURCE = {
    "OpenAI Blog":        7,
    "Google AI Blog":     7,
    "Microsoft AI Blog":  7,
    "Meta AI Engineering":7,
    "Anthropic Blog":     7,
    "TensorFlow Blog":    7,
    "The Verge AI":       2,
    "Wired AI":           2,
    "MIT Tech Review":    3,
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
        "url":    "https://blogs.microsoft.com/ai/feed/",
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
        "url":    "https://www.theverge.com/ai-artificial-intelligence/rss/index.xml",
        "name":   "The Verge AI",
        "weight": 1.4,
        "cap":    8,
    },
    {
        "url":    "https://www.wired.com/feed/category/ideas/latest/rss",
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
        "url":    "https://hnrss.org/best?q=AI+LLM+GPT+Claude+Gemini",
        "name":   "Hacker News AI",
        "weight": 1.3,
        "cap":    3,
    },
    {
        "url":    "https://blog.tensorflow.org/feeds/posts/default",
        "name":   "TensorFlow Blog",
        "weight": 1.5,
        "cap":    4,
    },
    {
        "url":    "https://arxiv.org/rss/cs.LG",
        "name":   "ArXiv ML",
        "weight": 1.4,
        "cap":    3,
    },
]

REDDIT_SOURCES = [
    {
        "subreddit": "MachineLearning",
        "name":      "r/MachineLearning",
        "weight":    1.3,
        "min_score": 80,
        "cap":       4,
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
        response = requests.get(source["url"], headers=HEADERS, timeout=12)
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
            title = _html.unescape(entry.get("title", "")).strip()
            link  = entry.get("link",  "").strip()
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

            content = (
                entry.get("content", [{}])[0].get("value", "")
                or entry.get("summary", "")
                or ""
            ).strip()

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
    url = f"https://www.reddit.com/r/{source['subreddit']}/top.json?t=day&limit=25"
    try:
        response = requests.get(url, headers=HEADERS, timeout=12)
        if response.status_code != 200:
            print(f"  ⚠️  HTTP {response.status_code} — skipping")
            return []

        posts = response.json().get("data", {}).get("children", [])
        articles = []

        for post in posts:
            if len(articles) >= source["cap"]:
                break

            data  = post.get("data", {})
            score = data.get("score", 0)

            if score < source["min_score"]:
                continue
            if data.get("is_self") and not data.get("selftext", "").strip():
                continue

            title = data.get("title", "").strip()
            # Clean Reddit tags like [P], [R], [D], etc.
            import re
            title = re.sub(r"\[.*?\]", "", title).strip()
            
            link  = data.get("url",   "").strip()
            if not title or not link:
                continue

            uid = _article_id(title, link)
            if uid in seen_ids:
                continue
            seen_ids.add(uid)

            fp = _title_fingerprint(title)

            # Check MongoDB history (same as RSS fetcher — prevents PM re-sends)
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

            content = data.get("selftext", "") or title

            articles.append({
                "id":            uid,
                "title":         title,
                "link":          link,
                "summary":       content[:1000],
                "source":        source["name"],
                "source_weight": source["weight"],
                "published":     "",
                "age":           "today",
                "upvotes":       score,
            })

        return articles

    except Exception as exc:
        print(f"  ❌ Reddit error: {exc}")
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
        print(f"📡 Fetching: {source['name']} (top/day, {source['min_score']}+ upvotes)")
        articles = _fetch_reddit_source(source, seen_ids, seen_fingerprints)
        all_articles.extend(articles)
        if articles:
            print(f"  ✅ {len(articles)} articles added")

    print(f"\n📦 Total unique articles fetched: {len(all_articles)}")
    return all_articles