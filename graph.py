# graph.py

from langgraph.graph import StateGraph
from typing import List, Dict, Optional
from typing_extensions import TypedDict

from fetch_news   import fetch_news
from summarize    import analyze_articles_parallel, rank_and_diversify, generate_final_output, cheap_prefilter


# ─────────────────────────────────────────────────────────────────────────────
# STATE
# ─────────────────────────────────────────────────────────────────────────────

class State(TypedDict, total=False):
    raw_articles:  List[Dict]   # straight from RSS
    analyzed:      List[Dict]   # filtered + scored articles
    top_articles:  List[Dict]   # top-N after diversification
    final_output:  str


# ─────────────────────────────────────────────────────────────────────────────
# NODES
# ─────────────────────────────────────────────────────────────────────────────

def fetch_node(state: State) -> State:
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  NODE 1 → FETCH")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    articles = fetch_news()
    state["raw_articles"] = articles
    return state


def analyze_node(state: State) -> State:
    """
    Combined filter + summarize + score node.
    Articles are deduped against previously-sent items by fetch_news()
    (MongoDB history). New articles are processed in parallel.
    """
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  NODE 2 → ANALYZE  (filter + score + summarize)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    raw = state.get("raw_articles", [])
    if not raw:
        state["analyzed"] = []
        return state

    # Stage 0: zero-cost keyword pre-filter (no LLM, no tokens)
    print(f"\n  🔍 Stage 0: keyword pre-filter on {len(raw)} articles...")
    raw, rejected_cheap = cheap_prefilter(raw)
    print(f"  🚫 Keyword filter removed {rejected_cheap} articles → {len(raw)} remain\n")

    # Process all surviving articles in parallel.
    # (Dedup against past digests is handled upstream in fetch_news via MongoDB.)
    all_analyzed = analyze_articles_parallel(raw) if raw else []
    state["analyzed"] = all_analyzed
    print(f"\n  ✅ Total kept articles: {len(all_analyzed)}")
    return state


def rank_node(state: State) -> State:
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  NODE 3 → RANK + DIVERSIFY")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    analyzed = state.get("analyzed", [])
    if not analyzed:
        state["top_articles"] = []
        return state

    top = rank_and_diversify(analyzed)

    print("\n  🏆 Final selection:")
    for i, art in enumerate(top, 1):
        print(f"  {i}. [{art['category']:8}] Score={art['total_score']:5.1f}  {art['title'][:55]}")

    # Persist the structured items (real category + score) so the thumbnail
    # gallery can render correct per-category colors without re-parsing text.
    try:
        from zoneinfo import ZoneInfo
        from datetime import datetime
        from db import save_digest_items
        ist = datetime.now(ZoneInfo("Asia/Kolkata"))
        date_str = f"{ist.strftime('%Y-%m-%d')}_{ist.strftime('%p')}"
        save_digest_items(date_str, "en", top)
    except Exception as e:
        print(f"  ⚠️ Could not persist digest items: {e}")

    state["top_articles"] = top
    return state


def output_node(state: State) -> State:
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  NODE 4 → GENERATE OUTPUT")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")

    top = state.get("top_articles", [])
    if not top:
        state["final_output"] = "⚠️  No high-signal news found today. Try again later."
        return state

    state["final_output"] = generate_final_output(top)
    return state


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH ASSEMBLY
# ─────────────────────────────────────────────────────────────────────────────

builder = StateGraph(State)

builder.add_node("fetch",   fetch_node)
builder.add_node("analyze", analyze_node)   # replaces summarize + score nodes
builder.add_node("rank",    rank_node)      # includes diversification
builder.add_node("output",  output_node)

builder.set_entry_point("fetch")

builder.add_edge("fetch",   "analyze")
builder.add_edge("analyze", "rank")
builder.add_edge("rank",    "output")

graph = builder.compile()