# main.py
import sys
import os

# Auto-activate venv if not running inside it
if not (sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import os
import sys
from datetime import date
from pathlib import Path
from graph import graph


def main():
    # --refresh: wipe cache so all articles re-analyzed with latest prompts
    if "--refresh" in sys.argv:
        cache_file = Path(".digest_cache.json")
        if cache_file.exists():
            cache_file.unlink()
            print("🗑️  Cache cleared — all articles will be re-analyzed.\n")
        else:
            print("ℹ️  No cache found — starting fresh.\n")

    print("\n🚀 Starting AI Tech Digest Agent...\n")

    result = graph.invoke({})

    digest = result.get("final_output", "No output generated.")

    # Save the selected top articles to the database history to prevent repeats
    top_articles = result.get("top_articles", [])
    try:
        from db import mark_article_as_sent
        from fetch_news import _title_fingerprint
        for art in top_articles:
            if "link" in art:
                fp = _title_fingerprint(art.get("title", "")) if "title" in art else None
                mark_article_as_sent(art["link"], fingerprint=fp)
    except Exception as e:
        print(f"⚠️ Could not save history to DB: {e}")

    print("\n" + "═" * 60)
    print(digest)
    print("═" * 60)

    # Save English digest
    today      = date.today().strftime("%Y-%m-%d")
    output_dir = "digests"
    os.makedirs(output_dir, exist_ok=True)
    filepath_en   = os.path.join(output_dir, f"digest_{today}_en.txt")
    
    with open(filepath_en, "w", encoding="utf-8") as f:
        f.write(digest)
    print(f"\n💾 English Digest saved to: {filepath_en}")

    # Generate Hindi digest
    from llm import llm_final
    from langchain_core.messages import HumanMessage
    
    print("🌍 Translating digest to Hindi...")
    translate_prompt = (
        "Translate the following tech news digest into Hindi. "
        "Keep the emojis, numbers, and formatting exactly the same. "
        "Do not translate company names or proper nouns (like 'Google', 'AI', 'Apple'). "
        "Ensure the Hindi flows naturally.\n\n"
        f"{digest}"
    )
    
    hi_response = llm_final.invoke([HumanMessage(content=translate_prompt)])
    digest_hi = hi_response.content
    
    filepath_hi = os.path.join(output_dir, f"digest_{today}_hi.txt")
    with open(filepath_hi, "w", encoding="utf-8") as f:
        f.write(digest_hi)
        
    print(f"💾 Hindi Digest saved to: {filepath_hi}")
    
    return digest


if __name__ == "__main__":
    main()