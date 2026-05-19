# graph.py

from langgraph.graph import StateGraph
from typing import TypedDict, List, Dict, Optional

from fetch_news   import fetch_news
from summarize    import analyze_articles_parallel, rank_and_diversify, generate_final_output, cheap_prefilter
from cache        import get_cached_result, set_cached_result, cache_stats


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
    print("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  NODE 1 → FETCH")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print(cache_stats())

    articles = fetch_news()
    state["raw_articles"] = articles
    return state


def analyze_node(state: State) -> State:
    """
    Combined filter + summarize + score node.
    Uses cache for articles seen in previous runs.
    New articles are processed in parallel.
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

    # Split into cached vs needs-processing
    cached_results:   list[dict] = []
    to_process:       list[dict] = []

    for art in raw:
        cached = get_cached_result(art["id"])
        if cached is None:
            # Not in cache at all — needs LLM processing
            to_process.append(art)
        elif cached:
            # Non-empty dict = article was previously kept
            cached_results.append(cached)
            print(f"  💾 CACHE-HIT: {art['title'][:60]}")
        else:
            # Empty dict {{}} = article was previously rejected — skip silently
            print(f"  💾 CACHE-REJECTED: {art['title'][:60]}")

    print(f"\n  📦 {len(cached_results)} from cache | {len(to_process)} new to process")

    # Process new articles in parallel
    fresh_results: list[dict] = []
    if to_process:
        fresh_results = analyze_articles_parallel(to_process)

        # Persist to cache
        processed_ids = {a["id"] for a in to_process}
        kept_ids      = {a["id"] for a in fresh_results}
        for art in to_process:
            if art["id"] in kept_ids:
                result = next(r for r in fresh_results if r["id"] == art["id"])
                set_cached_result(art["id"], result)
            else:
                set_cached_result(art["id"], {})  # {} = "rejected" sentinel

    all_analyzed = cached_results + fresh_results
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