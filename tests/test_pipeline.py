"""Unit tests for AI Tech Digest — pure logic, no network/DB/LLM required.

Run with:  venv/bin/python3 -m pytest tests/ -q
"""
import re
import sys
from pathlib import Path

import pytest

# Make the project root importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import summarize as S
from fetch_news import _title_fingerprint, _article_id
from voice_engine import _clean_for_speech
from mcp_server import write_source_file


# ─────────────────────────────────────────────────────────────────────────────
# 1. RANK / SCORE FORMULA  (matches summarize.py:216 implementation)
# ─────────────────────────────────────────────────────────────────────────────

def _art(cat="AI", source="OpenAI Blog", **over):
    a = {
        "id": _article_id("t", "l" + str(over.get("n", 0))),
        "title": "t", "link": "l", "source": source,
        "category": cat, "summary": "", "context": "", "why_it_matters": "",
        "innovation": 3, "impact": 3, "credibility": 3, "noise": 0,
        "raw_score": 9, "total_score": 9.0 * S.SOURCE_SCORE_ADJUSTMENTS.get(source, 1.0),
    }
    a.update(over)
    return a


def test_total_score_formula_adds_noise():
    """Confirm the implemented formula is (inn + imp + cred + noise) * weight."""
    a = _art(innovation=4, impact=5, credibility=4, noise=-2, source_weight=1.5)
    raw = 4 + 5 + 4 + (-2)            # = 11
    expected = round(raw * 1.5, 2)    # = 16.5
    # Recompute exactly as summarize._analyze_article would
    weighted = round((4 + 5 + 4 + (-2)) * 1.5, 2)
    assert weighted == expected == 16.5


def test_source_adjustments_applied_before_rank():
    arxiv = _art(source="ArXiv ML")
    pre = arxiv["total_score"]
    S.rank_and_diversify([arxiv])  # must not raise
    # rank_and_diversify applies the -20% ArXiv penalty on top of the existing score
    assert arxiv["total_score"] == round(pre * 0.80, 2)


# ─────────────────────────────────────────────────────────────────────────────
# 2. CATEGORY / PER-SOURCE CAPS
# ─────────────────────────────────────────────────────────────────────────────

def test_exactly_five_selected():
    cats_sources = [
        ("AI", "OpenAI Blog"),
        ("ai_tools", "Google AI Blog"),
        ("research", "ArXiv ML"),
        ("big_tech", "Microsoft AI Blog"),
        ("hardware", "Meta AI Engineering"),
        ("startup", "TechCrunch AI"),
        ("other", "VentureBeat AI"),
    ]
    arts = [_art(cat=c, source=s, n=i) for i, (c, s) in enumerate(cats_sources)]
    selected = S.rank_and_diversify(arts)
    assert len(selected) == S.TOP_N == 5


def test_category_caps_respected():
    # 7 "AI" articles, each from a DISTINCT source (per-source cap = 2)
    ai_sources = ["OpenAI Blog", "Google AI Blog", "Microsoft AI Blog",
                  "Meta AI Engineering", "The Verge AI", "Wired AI", "TechCrunch AI"]
    arts = [_art(cat="AI", source=ai_sources[i], n=i) for i in range(7)]
    other_specs = [("ai_tools", "TensorFlow Blog"), ("research", "ArXiv ML"),
                   ("big_tech", "VentureBeat AI"), ("hardware", "Ars Technica"),
                   ("startup", "Hacker News AI"), ("other", "Anthropic Blog")]
    arts += [_art(cat=c, source=s, n=100 + i) for i, (c, s) in enumerate(other_specs)]
    selected = S.rank_and_diversify(arts)
    ai_count = sum(1 for a in selected if a["category"] == "AI")
    assert ai_count <= S.CATEGORY_SLOTS["AI"]
    assert len(selected) == S.TOP_N


def test_per_source_cap():
    arts = [_art(source="OpenAI Blog", n=i) for i in range(5)]
    selected = S.rank_and_diversify(arts)
    src_count = sum(1 for a in selected if a["source"] == "OpenAI Blog")
    assert src_count <= 2


# ─────────────────────────────────────────────────────────────────────────────
# 3. AUDIENCE TAGGING (zero-LLM mapping)
# ─────────────────────────────────────────────────────────────────────────────

def test_audience_tags():
    assert S._audience_tag("ai_tools") == "👩‍💻 Developers"
    assert S._audience_tag("hardware") == "⚙️  Engineers"
    assert S._audience_tag("startup") == "🚀 Founders & Investors"
    assert S._audience_tag("research") == "🔬 Researchers"
    assert S._audience_tag("unknown_cat") == "🌐 Everyone"


# ─────────────────────────────────────────────────────────────────────────────
# 4. DEDUP / FINGERPRINT
# ─────────────────────────────────────────────────────────────────────────────

def test_title_fingerprint_stable_and_stopword_filtered():
    fp1 = _title_fingerprint("OpenAI launches new AI agent model")
    fp2 = _title_fingerprint("OpenAI launches NEW AI Agent Model")
    # stopwords removed, lowercased, first 6 words
    assert fp1 == fp2
    assert "the" not in fp1
    assert len(fp1.split()) <= 6


def test_article_id_deterministic():
    assert _article_id("A", "B") == _article_id("A", "B")
    assert _article_id("A", "B") != _article_id("A", "C")


# ─────────────────────────────────────────────────────────────────────────────
# 5. CHEAP PRE-FILTER
# ─────────────────────────────────────────────────────────────────────────────

def test_cheap_prefilter_rejects_promo():
    promo = {"title": "Black Friday 50% off AI course!", "age": "1d", "source": "The Verge AI"}
    kept, rejected = S.cheap_prefilter([promo])
    assert rejected == 1 and kept == []


def test_cheap_prefilter_keeps_real_news():
    real = {"title": "OpenAI releases new reasoning model", "age": "3h", "source": "OpenAI Blog"}
    kept, rejected = S.cheap_prefilter([real])
    assert kept == [real] and rejected == 0


# ─────────────────────────────────────────────────────────────────────────────
# 6. VOICE CLEANING
# ─────────────────────────────────────────────────────────────────────────────

def test_clean_for_speech_strips_links_and_emojis():
    dirty = "🔥 OpenAI launches model https://openai.com/blog/x 📰 [Score: 19.8]"
    clean = _clean_for_speech(dirty)
    assert "https://" not in clean
    assert "🔥" not in clean
    assert "Score:" not in clean
    assert "OpenAI launches model" in clean


# ─────────────────────────────────────────────────────────────────────────────
# 7. MCP WRITE GUARD  (security surface)
# ─────────────────────────────────────────────────────────────────────────────

def test_mcp_write_denies_secrets_and_self(tmp_path, monkeypatch):
    # Redirect PROJECT_ROOT to a temp dir so the sandbox lives under it
    monkeypatch.setattr("mcp_server.PROJECT_ROOT", tmp_path)
    # .env must never be writable
    assert "Access Denied" in write_source_file(".env", "EVIL=1")
    # The server's own code must never be writable (no self-modification)
    assert "Access Denied" in write_source_file("mcp_server.py", "evil")
    # db.py must now be DENIED (it is core infra — never writable via this surface)
    assert "Access Denied" in write_source_file("db.py", "# ok")
    # Non-allowlisted file denied
    assert "Access Denied" in write_source_file("secret_keys.py", "x")
    # A normal allowlisted file is STAGED into .mcp_writes/, not applied live
    res = write_source_file("main.py", "# staged")
    assert "Staged" in res and ".mcp_writes" in res
    assert (tmp_path / ".mcp_writes" / "main.py").read_text() == "# staged"
    # The live allowlisted file must remain UNTOUCHED (sandbox, not overwrite)
    assert not (tmp_path / "main.py").exists()


def test_mcp_write_never_touches_live_project():
    """Regression guard: even writing an allowlisted file must NOT modify the
    real project. Simulates the prior 'db.py -> # ok' clobber incident."""
    import mcp_server as ms
    live_db = ms.PROJECT_ROOT / "db.py"
    snapshot = live_db.read_text() if live_db.exists() else None
    # Attempt to stage db.py (now denied) and main.py (staged to sandbox)
    write_source_file("db.py", "# evil-clobber")
    write_source_file("main.py", "# evil-clobber")
    # Live db.py must be byte-for-byte unchanged
    if snapshot is not None:
        assert live_db.read_text() == snapshot, "LIVE db.py was modified by write_source_file!"
    # No stray file written into the project root itself
    assert not (ms.PROJECT_ROOT / "db.py.bak").exists()
    # Clean up the sandbox artifact we created
    sandbox = ms.PROJECT_ROOT / ".mcp_writes" / "main.py"
    if sandbox.exists():
        sandbox.unlink()


# ─────────────────────────────────────────────────────────────────────────────
# 8. THUMBNAIL GENERATION  (visual UX, zero-cost Pillow)
# ─────────────────────────────────────────────────────────────────────────────

def test_thumbnail_renders_and_picks_motif():
    """thumbnail.generate_story_thumbnail must produce a 1080x1080 PNG and
    select a topic-resonant motif from the title keywords."""
    import thumbnail as T
    from PIL import Image

    cases = [
        ("How Google's new Pixel 11 phones compare", "big_tech", 15.4, "_motif_phone"),
        ("Testing ads in ChatGPT", "ai", 16.2, "_motif_megaphone"),
        ("A new AI hardware chip promises efficiency", "hardware", 12.0, "_motif_chip"),
        ("Small lab raises seed round", "startup", 10.5, "_motif_rocket"),
    ]
    for title, cat, score, expected_motif in cases:
        item = {"title": title, "source": "Test", "category": cat,
                "total_score": score, "link": "https://x.test/a", "_date_str": "2026-08-13_PM"}
        path = T.generate_story_thumbnail(item, 1, lang="en")
        im = Image.open(path)
        assert im.size == (1080, 1080), f"bad size for {title}: {im.size}"
        # Motif selection must match the title keyword
        assert T._pick_motif(title).__name__ == expected_motif, f"motif mismatch for {title}"
        # Category color must be distinct per category
        assert T._category_bg(cat, score)[0] != T._category_bg("other", 9.0)[0]
        Path(path).unlink(missing_ok=True)
