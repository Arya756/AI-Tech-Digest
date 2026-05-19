# summarize.py

import re
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from llm import llm, llm_final


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 0 — CHEAP PRE-FILTER (zero LLM calls, zero tokens)
# Reject obvious junk by title keywords before touching the API.
# This alone eliminates ~30% of Verge/TechCrunch noise (coupons, deals, etc.)
# ─────────────────────────────────────────────────────────────────────────────

_REJECT_TITLE_KEYWORDS = [
    "promo code", "coupon", "discount", "% off", "deal of",
    "black friday", "cyber monday", "sale:", "savings",
    "recipe", "best movies", "best tv", "gift guide",
    "review: ", "hands-on:", "unboxing",
    "wallpaper", "ringtone", "theme pack",
    "you need to know", "here's why", "everything you need",
]

_REJECT_TITLE_PATTERNS = [
    re.compile(r"\b\d+%\s+off\b", re.IGNORECASE),
    re.compile(r"\bpromo\s+code\b", re.IGNORECASE),
    re.compile(r"\bcoupon\b", re.IGNORECASE),
]

_ARXIV_REJECT_PATTERNS = [
    re.compile(r"\bfederated\b.*\bmultimodal\b", re.IGNORECASE),
    re.compile(r"\bcopula.aligned\b", re.IGNORECASE),
    re.compile(r"\bsize complexity\b", re.IGNORECASE),
    re.compile(r"\bdecidability\b", re.IGNORECASE),
    re.compile(r"\bparticipatory evaluation\b", re.IGNORECASE),
]


def cheap_prefilter(articles: list[dict]) -> tuple[list[dict], int]:
    """
    Zero-cost keyword pre-filter. Logs article age for transparency.
    Returns (kept_articles, rejected_count).
    """
    kept = []
    rejected = 0
    for art in articles:
        title_lower = art["title"].lower()
        age    = art.get("age", "")
        source = art.get("source", "")

        drop = any(kw in title_lower for kw in _REJECT_TITLE_KEYWORDS)
        if not drop:
            drop = any(p.search(art["title"]) for p in _REJECT_TITLE_PATTERNS)
        if not drop and source == "ArXiv ML":
            drop = any(p.search(art["title"]) for p in _ARXIV_REJECT_PATTERNS)

        if drop:
            print(f"  🚫 PRE-FILTER: {art['title'][:65]}")
            rejected += 1
        else:
            age_tag = f" [{age}]" if age else ""
            print(f"  ✓  PASS{age_tag}: {art['title'][:58]}")
            kept.append(art)
    return kept, rejected


# ─────────────────────────────────────────────────────────────────────────────
# COMBINED ANALYSIS PROMPT
# One LLM call per article: filter + summarize + score + category + insight.
# Prompt is kept SHORT to minimise token usage on Groq free tier.
# ─────────────────────────────────────────────────────────────────────────────

ANALYSIS_PROMPT = """You are a senior tech analyst. Analyze this article strictly.
Return ONLY valid JSON — no markdown fences, no explanation, nothing else.

Title: {title}
Content: {content}
Source: {source}

JSON schema (use exact keys):
{{"keep":true,"reject_reason":null,"category":"AI","summary":"...","context":"...","innovation":3,"impact":3,"credibility":3,"noise":0,"why_it_matters":"..."}}

CATEGORY — pick the MOST SPECIFIC one that fits:
- "AI"       → new AI/ML model releases, LLM products, AI agent launches, AI safety findings
- "infra"    → data centers, GPUs/chips, cloud shifts, networking, security vulnerabilities, supply chain attacks
- "startup"  → funding rounds (must include $ amount), new company launches, acqui-hires, founder moves
- "big_tech" → Google/Apple/Meta/Microsoft/Amazon/Nvidia product announcements or strategy
- "research" → peer-reviewed papers, scientific breakthroughs, benchmark results
- "other"    → everything else

BOUNDARY EXAMPLES (memorise these):
- "OpenAI builds sandbox for Codex" = "AI" (new AI product/tool)
- "npm supply chain attack" = "infra" (security incident)
- "Google Finance expands to Europe" = "big_tech" (Google product launch)
- "AutoScout24 uses ChatGPT" = "other" (customer case study, NOT news)
- "Meta open-sources GPU comms lib" = "infra" (compute infrastructure)
- "$8M seed round" = "startup" (has $ amount = funding)
- "Varda Space commercializes drug manufacturing" = "other" (business deal, not a funding round)
Do NOT assign "AI" just because AI is mentioned. Ask: is this a NEW AI PRODUCT or MODEL?

Rules:
- keep=true ONLY for: new AI/ML model launches, infra breakthroughs, major funding (>$50M), tech research with broad real-world impact, big tech strategy shifts
- keep=false for: biology/archaeology/physics/chemistry research (NOT tech), customer case studies, opinion pieces, minor feature updates, rumours, small funding (<$20M), think-pieces, how-to posts, legal/court proceedings
- summary: exactly 2 sentences, hard facts only, include specific names/numbers
- context: 1-2 sentences of BACKGROUND for a non-technical listener. Explain what key terms mean, what happened before this story, or why this topic matters historically. Skip if the story needs no background. Example: "A supply chain attack poisons a widely-used software package so every app that installs it gets infected. npm is the world's largest JavaScript package registry with over 2 million packages."
- innovation 0-5: technical novelty (5=first of its kind, 0=incremental)
- impact 0-5: industry-wide magnitude (5=changes the game, 1=niche only)
- credibility 0-5: firmness of announcement (official+confirmed=5, rumour=1)
- noise -5-0: penalise marketing/case-study/hype content (0=clean, -5=pure noise)
- why_it_matters: 8-12 words. WHO loses or gains WHAT specifically.
  FORBIDDEN PHRASES: "gain insights", "gain faster X", "advances technology", "enhances experience", "transforms X"
  GOOD: "OpenAI loses video market to competitor 10x cheaper"
  GOOD: "npm maintainers must audit 3M dependent packages immediately"
  GOOD: "AMD closes CUDA gap, threatening Nvidia monopoly on AI training"
- If unsure on keep → false"""


# ─────────────────────────────────────────────────────────────────────────────
# RATE-LIMIT-AWARE TOKEN BUCKET
# Groq free tier: 12,000 TPM.  Each request ≈ 400-600 tokens in + ~200 out.
# We conservatively budget 700 tokens/request → max ~17 req/min.
# With 3 workers and 3.5s sleep between batches we stay well under.
# ─────────────────────────────────────────────────────────────────────────────

_GROQ_TPM_LIMIT    = 12_000
_TOKENS_PER_REQ    = 700          # conservative estimate
_MAX_WORKERS       = 3            # safe concurrency for free tier
_INTER_BATCH_SLEEP = 4.0          # seconds between worker-batch completions
_RETRY_BASE_SLEEP  = 3.0          # base sleep on 429, doubles each retry


def _safe_parse_json(text: str) -> dict | None:
    """
    Robust JSON extractor — handles:
      • clean JSON
      • ```json ... ``` fences
      • leading/trailing prose around the JSON object
    """
    text = text.strip()

    # Strip markdown fences
    text = re.sub(r"^```(?:json)?\s*\n?", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\n?```\s*$", "", text)

    # Attempt 1: direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Attempt 2: extract first {...} block (handles prose prefix/suffix)
    match = re.search(r"\{[^{}]*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    # Attempt 3: greedy nested-brace extraction
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(text[start : i + 1])
                    except json.JSONDecodeError:
                        break

    return None


def _analyze_article(article: dict) -> dict | None:
    """
    Single LLM call per article.
    Handles 429 rate-limit errors with exponential backoff.
    Returns enriched article dict, or None if rejected/failed.
    """
    prompt = ANALYSIS_PROMPT.format(
        title=article["title"],
        content=article["summary"][:600],   # trim content to save tokens
        source=article["source"],
    )

    sleep = _RETRY_BASE_SLEEP

    for attempt in range(4):   # up to 4 attempts per article
        try:
            response = llm.invoke(prompt)
            content_str = response.content
            if not isinstance(content_str, str):
                raise TypeError("Expected string response from LLM")
            parsed   = _safe_parse_json(content_str)

            if parsed is None:
                print(f"  ⚠️  JSON parse failed (attempt {attempt+1}): {article['title'][:55]}")
                time.sleep(1.0)
                continue

            if not parsed.get("keep", False):
                return None

            raw_score = (
                parsed.get("innovation",  0)
                + parsed.get("impact",    0)
                + parsed.get("credibility", 0)
                + parsed.get("noise",     0)
            )
            weighted_score = round(raw_score * article.get("source_weight", 1.0), 2)

            return {
                "id":             article["id"],
                "title":          article["title"],
                "link":           article["link"],
                "source":         article["source"],
                "category":       parsed.get("category", "other"),
                "summary":        parsed.get("summary", ""),
                "context":        parsed.get("context", ""),   # background knowledge
                "why_it_matters": parsed.get("why_it_matters", ""),
                "innovation":     parsed.get("innovation", 0),
                "impact":         parsed.get("impact", 0),
                "credibility":    parsed.get("credibility", 0),
                "noise":          parsed.get("noise", 0),
                "raw_score":      raw_score,
                "total_score":    weighted_score,
            }

        except Exception as exc:
            err_str = str(exc)
            if "429" in err_str or "rate_limit" in err_str.lower():
                # Extract suggested wait time from Groq error message if present
                wait_match = re.search(r"try again in\s+([\d.]+)s", err_str, re.IGNORECASE)
                groq_wait  = float(wait_match.group(1)) + 0.5 if wait_match else sleep
                actual_wait = max(groq_wait, sleep)
                print(f"  ⏳ Rate limited — waiting {actual_wait:.1f}s (attempt {attempt+1})")
                time.sleep(actual_wait)
                sleep = min(sleep * 2, 20)   # exponential backoff, cap at 20s
            else:
                print(f"  ❌ LLM error (attempt {attempt+1}): {err_str[:80]}")
                time.sleep(1.5)

    print(f"  💀 Gave up after 4 attempts: {article['title'][:55]}")
    return None


# ─────────────────────────────────────────────────────────────────────────────
# RATE-SAFE PARALLEL RUNNER
# Uses small batches with a pause between them to stay under TPM limit.
# ─────────────────────────────────────────────────────────────────────────────

def analyze_articles_parallel(articles: list[dict]) -> list[dict]:
    """
    Process articles in small concurrent batches, pausing between batches
    to avoid saturating Groq's 12K TPM free-tier limit.
    """
    results: list[dict] = []
    batch_size = _MAX_WORKERS   # process N at a time
    total      = len(articles)

    print(f"\n🔬 Analyzing {total} articles in batches of {batch_size}...")

    for batch_start in range(0, total, batch_size):
        batch = articles[batch_start : batch_start + batch_size]
        batch_num = batch_start // batch_size + 1
        total_batches = (total + batch_size - 1) // batch_size
        print(f"\n  📦 Batch {batch_num}/{total_batches}  ({len(batch)} articles)")

        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_art = {executor.submit(_analyze_article, art): art for art in batch}
            for future in as_completed(future_to_art):
                art = future_to_art[future]
                try:
                    result = future.result()
                    if result:
                        results.append(result)
                        print(f"  ✅ KEPT  [{result['category']:8}] {result['title'][:55]}")
                    else:
                        print(f"  🗑️  DROP          {art['title'][:55]}")
                except Exception as exc:
                    print(f"  ❌ Unexpected: {exc}")

        # Pause between batches to let the token bucket refill
        if batch_start + batch_size < total:
            print(f"  ⏸️  Cooling down {_INTER_BATCH_SLEEP}s before next batch...")
            time.sleep(_INTER_BATCH_SLEEP)

    print(f"\n📊 {len(results)}/{total} articles passed LLM filter")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# DIVERSIFICATION  (prevents all-AI or all-startup output)
# ─────────────────────────────────────────────────────────────────────────────

CATEGORY_SLOTS = {
    "AI":       3,
    "infra":    2,
    "big_tech": 2,
    "startup":  2,
    "research": 1,   # max 1 paper per digest
    "other":    1,
}
TOP_N = 5

# Source-level score adjustments applied before ranking.
# ArXiv papers score high on innovation but low real-world impact today.
SOURCE_SCORE_ADJUSTMENTS = {
    "ArXiv ML":          0.80,   # -20%: papers rarely matter same day
    "r/MachineLearning": 0.90,   # -10%: community signal, not primary
}


def rank_and_diversify(analyzed: list[dict]) -> list[dict]:
    """
    Sort by total_score, then pick top-N enforcing category caps.
    Applies source-level score adjustments before sorting.
    """
    if not analyzed:
        return []

    # Apply source-level adjustments
    for art in analyzed:
        adj = SOURCE_SCORE_ADJUSTMENTS.get(art["source"], 1.0)
        if adj != 1.0:
            art["total_score"] = round(art["total_score"] * adj, 2)

    from collections import Counter
    dist = Counter(a["category"] for a in analyzed)
    print(f"\n  📊 Category distribution: {dict(dist)}")

    sorted_articles = sorted(analyzed, key=lambda x: x["total_score"], reverse=True)

    selected: list[dict] = []
    category_counts: dict[str, int] = {}
    source_counts:   dict[str, int] = {}
    MAX_PER_SOURCE = 2   # no single source dominates the digest

    # First pass: enforce category caps AND per-source cap
    for art in sorted_articles:
        cat    = art["category"]
        source = art["source"]
        if category_counts.get(cat, 0) >= CATEGORY_SLOTS.get(cat, 1):
            continue
        if source_counts.get(source, 0) >= MAX_PER_SOURCE:
            continue
        selected.append(art)
        category_counts[cat]  = category_counts.get(cat, 0)  + 1
        source_counts[source] = source_counts.get(source, 0) + 1
        if len(selected) >= TOP_N:
            break

    # Second pass: fill remaining slots (relax source cap only, keep category cap)
    if len(selected) < TOP_N:
        for art in sorted_articles:
            if art in selected:
                continue
            cat = art["category"]
            if category_counts.get(cat, 0) >= CATEGORY_SLOTS.get(cat, 1):
                continue
            selected.append(art)
            category_counts[cat] = category_counts.get(cat, 0) + 1
            if len(selected) >= TOP_N:
                break

    # Third pass: absolute fallback — fill by pure score if still gaps
    if len(selected) < TOP_N:
        for art in sorted_articles:
            if art not in selected:
                selected.append(art)
            if len(selected) >= TOP_N:
                break

    return selected

# ─────────────────────────────────────────────────────────────────────────────
# FINAL DIGEST GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def _priority_tag(score: float) -> str:
    """
    Thresholds calibrated for weighted scores (source_weight applied).
    Raw max = 5+5+5+0 = 15. With weight 1.4 → max ~21.
    Typical "important" article: raw 10-12 → weighted 12-17.
    CRITICAL reserved for genuine breakthroughs (raw 13+).
    """
    if score >= 17:
        return "🔥 CRITICAL"
    elif score >= 11:
        return "⚡ IMPORTANT"
    else:
        return "📌 NOTE"


def generate_final_output(top_articles: list[dict]) -> str:
    """Build the formatted digest string from pre-analyzed articles."""
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = datetime.now(ZoneInfo("Asia/Kolkata")).strftime("%B %d, %Y")
    lines = [f"🔥 DAILY TECH DIGEST — {today}\n", "=" * 50 + "\n"]

    for i, art in enumerate(top_articles, 1):
        tag   = _priority_tag(art["total_score"])
        score = art["total_score"]

        lines.append(f"{i}. {tag}  [Score: {score}]")
        lines.append(f"   📰 {art['title']}")
        lines.append(f"   🏷️  {art['category'].upper()} | 📡 {art['source']}")
        lines.append(f"   📝 {art['summary']}")
        context = art.get("context", "").strip()
        if context:
            lines.append(f"   🧠 {context}")
        lines.append(f"   👉 {art['why_it_matters']}")
        lines.append(f"   🔗 {art['link']}")
        lines.append("")

    lines.append("=" * 50)
    lines.append("Generated by AI Tech Digest Agent")

    return "\n".join(lines)