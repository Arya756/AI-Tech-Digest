#!/usr/bin/env python3
# voice_engine.py
"""
Converts the AI Tech Digest into a natural-sounding voice note.

Supports two input modes:
  1. From a list of article dicts (direct integration with graph.py pipeline)
  2. From a digest .txt file (standalone mode)

Output:
  - digests/digest_YYYY-MM-DD.ogg  (Telegram native voice note)
  - digests/digest_YYYY-MM-DD.mp3  (standard fallback)

Usage:
  python3 voice_engine.py                        # reads today's digest file
  python3 voice_engine.py --date 2026-05-14      # reads a specific date's file
"""

import asyncio
import re
import os
import sys
import argparse
from datetime import date, datetime
from pathlib import Path

import edge_tts

# ─────────────────────────────────────────────────────────────────────────────
# VOICE CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Voices that sound best for a tech news anchor style.
# Run `edge-tts --list-voices` to explore more options.
VOICE_OPTIONS = {
    "ava":     "en-US-AvaNeural",       # Warm, expressive female (default)
    "andrew":  "en-US-AndrewNeural",    # Deep, authoritative male
    "aria":    "en-US-AriaNeural",      # Professional female
    "sonia":   "en-GB-SoniaNeural",     # British female, very polished
    "ryan":    "en-GB-RyanNeural",      # British male, BBC-style
    "jenny":   "en-US-JennyNeural",     # Warm, friendly female
}

DEFAULT_VOICE = "ava"

# Fine-tune speech delivery
SPEECH_RATE  = "+0%"    # Normal pace. Use "+10%" to speed up, "-10%" to slow down
SPEECH_PITCH = "+0Hz"   # Natural pitch


# ─────────────────────────────────────────────────────────────────────────────
# TEXT CLEANING — strips symbols that sound terrible when spoken aloud
# ─────────────────────────────────────────────────────────────────────────────

def _clean_for_speech(text: str) -> str:
    """
    Remove emojis, markdown symbols, scores, URLs, and other visual
    noise that sounds awkward in spoken audio.
    """
    # Strip URLs
    text = re.sub(r"https?://\S+", "", text)

    # Strip emojis and symbols while preserving words like "OpenAI"
    # Targets: pictographs, dingbats, enclosed chars, misc symbols, transport, etc.
    text = re.sub(
        r"[\U0001F000-\U0001FFFF"  # emoticons, symbols, pictographs
        r"\u2600-\u26FF"           # misc symbols (⚡🔥 etc.)
        r"\u2700-\u27BF"           # dingbats
        r"\u2B00-\u2BFF"           # misc arrows/symbols
        r"\u25A0-\u25FF"           # geometric shapes
        r"\u2190-\u21FF"           # arrows
        r"\u2300-\u23FF"           # misc technical
        r"\uFE00-\uFE0F"           # variation selectors
        r"]+", " ", text, flags=re.UNICODE
    )

    # Strip score tags like [Score: 19.8] or [18h ago]
    text = re.sub(r"\[Score:.*?\]", "", text)
    text = re.sub(r"\[\d+h? ago\]", "", text)
    text = re.sub(r"\[\d+d ago\]", "", text)

    # Strip upvote tags like [103⬆]
    text = re.sub(r"\[\d+[^\]]*\]", "", text)

    # Strip separator lines (======, ────)
    text = re.sub(r"[=─]{4,}", "", text)

    # Strip markdown-style headers and bullets
    text = re.sub(r"^\s*[-*•]\s+", "", text, flags=re.MULTILINE)

    # Strip leftover category/priority label prefixes from digest format
    # Use word boundaries so "AI" in "OpenAI" is NOT stripped
    for label in ["CRITICAL", "IMPORTANT", "NOTE", "RESEARCH", "BIG_TECH",
                  "INFRA", "STARTUP", "OTHER"]:
        text = re.sub(rf"\b{label}\b", "", text)
    # Strip standalone "AI" only when it appears as a category tag (all caps, surrounded by spaces/pipes)
    text = re.sub(r"(?<=[|\s])AI(?=[|\s])", "", text)

    # Clean pipe separators
    text = text.replace("|", "")

    # Collapse multiple whitespace / blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# ─────────────────────────────────────────────────────────────────────────────
# SCRIPT BUILDER — turns articles into a natural newscast script
# ─────────────────────────────────────────────────────────────────────────────

def build_script_from_articles(articles: list[dict], script_date: str = "", lang: str = "en") -> str:
    """
    Build a spoken-word newscast script from a list of analyzed article dicts.
    Called directly from graph.py or the Telegram bot after the pipeline runs.

    Each article dict is expected to have:
      title, summary, why_it_matters, source, category
    """
    today_str = script_date or date.today().strftime("%B %d, %Y")
    total     = len(articles)

    lines = []

    # ── Intro ──────────────────────────────────────────────────────────────
    if lang == "hi":
        lines.append(
            f"सुप्रभात। {today_str} के दैनिक एआई तकनीकी समाचार में आपका स्वागत है। "
            f"आज मेरे पास {total} महत्वपूर्ण खबरें हैं। चलिए शुरू करते हैं।"
        )
        ordinals = ["पहली खबर", "दूसरी खबर", "तीसरी खबर", "चौथी खबर", "पांचवीं खबर",
                    "छठी खबर", "सातवीं खबर", "आठवीं खबर", "नौवीं खबर", "दसवीं खबर"]
    else:
        lines.append(
            f"Good morning. Welcome to the Daily AI Tech Digest for {today_str}. "
            f"Today I have {total} stories that matter. Let's get into it."
        )
        ordinals = ["First", "Second", "Third", "Fourth", "Fifth",
                    "Sixth", "Seventh", "Eighth", "Ninth", "Tenth"]
    lines.append("")

    # ── Stories ────────────────────────────────────────────────────────────
    for i, art in enumerate(articles):
        if lang == "hi":
            ordinal  = ordinals[i] if i < len(ordinals) else f"खबर {i+1}"
        else:
            ordinal  = ordinals[i] if i < len(ordinals) else f"Story {i+1}"
            
        title    = _clean_for_speech(art.get("title", ""))
        summary  = _clean_for_speech(art.get("summary", ""))
        impact   = _clean_for_speech(art.get("why_it_matters", ""))
        source   = _clean_for_speech(art.get("source", ""))
        context  = _clean_for_speech(art.get("context", ""))

        if lang == "hi":
            lines.append(f"{ordinal}।")
            lines.append(f"{title}।")
            lines.append(f"{source} द्वारा रिपोर्ट किया गया।")
            if context:
                lines.append(f"थोड़ी पृष्ठभूमि: {context}")
            lines.append(f"{summary}")
            if impact and impact.lower() not in summary.lower():
                lines.append(f"यह क्यों मायने रखता है: {impact}।")
        else:
            lines.append(f"{ordinal} up.")
            lines.append(f"{title}.")
            lines.append(f"Reported by {source}.")
            if context:
                lines.append(f"A bit of background: {context}")
            lines.append(f"{summary}")
            if impact and impact.lower() not in summary.lower():
                lines.append(f"Why it matters: {impact}.")
        lines.append("")

    # ── Outro ──────────────────────────────────────────────────────────────
    if lang == "hi":
        lines.append(
            "यह था आज का एआई तकनीकी समाचार। "
            "जिज्ञासु रहें, आगे रहें। कल मिलते हैं।"
        )
    else:
        lines.append(
            "That's your AI Tech Digest for today. "
            "Stay curious, stay ahead. See you tomorrow."
        )

    return "\n".join(lines)


def build_script_from_digest_file(digest_path: Path, lang: str = "en") -> str:
    """
    Parse a saved digest .txt file and convert it to a clean spoken script.
    Used in standalone mode (`python3 voice_engine.py`).

    Digest line format:
      1. 🔥 CRITICAL  [Score: 19.8]
         📰 Title here
         🏷️  CATEGORY | 📡 Source Name
         📝 Summary text here
         👉 Why it matters
         🔗 https://link
    """
    raw = digest_path.read_text(encoding="utf-8")

    # Extract the date from the header line
    date_match = re.search(r"DAILY TECH DIGEST.*?(\w+ \d+, \d+)", raw)
    today_str  = date_match.group(1) if date_match else date.today().strftime("%B %d, %Y")

    articles = []

    # Each story block starts with a line like "1. 🔥 CRITICAL..."
    story_blocks = re.split(r"(?m)^\d+\.", raw)

    for block in story_blocks[1:]:  # skip header
        title   = ""
        source  = ""
        summary = ""
        context = ""   # 🧠 background field
        impact  = ""

        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Title line starts with 📰
            if "\U0001F4F0" in line and not title:  # 📰
                title = re.sub(r"^\U0001F4F0\s*", "", line).strip()

            # Category/Source line: 🏷️  CATEGORY | 📡 Source Name
            elif "\U0001F3F7" in line or "\U0001F4E1" in line:  # 🏷️ or 📡
                if "|" in line:
                    source_raw = line.split("|")[-1].strip()
                    source = re.sub(r"[\U0001F4E1\s]+", " ", source_raw).strip()

            # Summary line starts with 📝
            elif "\U0001F4DD" in line and not summary:  # 📝
                summary = re.sub(r"^\U0001F4DD\s*", "", line).strip()

            # Context line starts with 🧠  ← THE MISSING HANDLER
            elif "\U0001F9E0" in line and not context:  # 🧠
                context = re.sub(r"^\U0001F9E0\s*", "", line).strip()

            # Why-it-matters line starts with 👉
            elif "\U0001F449" in line and not impact:  # 👉
                impact = re.sub(r"^\U0001F449\s*", "", line).strip()

            # Skip URL lines
            elif line.startswith("http"):
                continue

        if title or summary:
            articles.append({
                "title":          title,
                "summary":        summary,
                "context":        context,
                "why_it_matters": impact,
                "source":         source,
            })

    return build_script_from_articles(articles, script_date=today_str, lang=lang)



# ─────────────────────────────────────────────────────────────────────────────
# TTS ENGINE — generates the actual audio file
# ─────────────────────────────────────────────────────────────────────────────

async def _synthesize(script: str, output_path: Path, voice_key: str = DEFAULT_VOICE) -> None:
    """Use edge-tts to synthesize speech and save to file."""
    # Use the mapped voice if it exists, otherwise use the voice_key directly
    voice = VOICE_OPTIONS.get(voice_key, voice_key)
    print(f"  🎙️  Voice: {voice}")
    print(f"  📄 Script length: {len(script)} characters (~{len(script)//5} words)")

    communicate = edge_tts.Communicate(script, voice, rate=SPEECH_RATE, pitch=SPEECH_PITCH)
    await communicate.save(str(output_path))


def generate_voice_note(
    articles:   list[dict] | None = None,
    digest_path: Path | None       = None,
    output_dir:  str               = "digests",
    voice_key:   str               = DEFAULT_VOICE,
    date_str:    str | None        = None,
    lang:        str               = "en",
) -> Path:
    """
    Main entry point.

    Accepts EITHER:
      - articles: list of article dicts from the pipeline
      - digest_path: path to a saved .txt digest file

    Returns the Path to the generated .mp3 file.
    """
    os.makedirs(output_dir, exist_ok=True)
    today = date_str or date.today().strftime("%Y-%m-%d")

    # Build the spoken script
    if articles is not None:
        print("  📝 Building script from article data...")
        script = build_script_from_articles(articles, script_date=today, lang=lang)
    elif digest_path is not None:
        print(f"  📝 Building script from {digest_path.name}...")
        detected_lang = "hi" if str(digest_path).endswith("_hi.txt") else "en"
        script = build_script_from_digest_file(digest_path, lang=detected_lang)
    else:
        raise ValueError("Provide either `articles` or `digest_path`.")

    print("\n─── SPOKEN SCRIPT PREVIEW (first 400 chars) ───")
    print(script[:400] + "...")
    print("───────────────────────────────────────────────\n")

    # Save the script as a .txt for debugging / review
    script_path = Path(output_dir) / f"script_{today}.txt"
    script_path.write_text(script, encoding="utf-8")
    print(f"  💾 Script saved to: {script_path}")

    # Generate audio
    if digest_path:
        mp3_name = digest_path.with_suffix(".mp3").name
    else:
        mp3_name = f"digest_{today}_en.mp3"
        
    mp3_path = Path(output_dir) / mp3_name
    print(f"  🔊 Generating audio → {mp3_path}")
    
    try:
        loop = asyncio.get_running_loop()
        # If we are in an event loop, we can't use asyncio.run.
        # We need to run the synthesis and wait for it.
        # Note: Since this function is sync, we use a trick or just tell the user to use the async version.
        # Actually, for simplicity in this project, let's just use a thread if loop is running.
        import threading
        def run_in_new_loop():
            asyncio.run(_synthesize(script, mp3_path, voice_key=voice_key))
        
        thread = threading.Thread(target=run_in_new_loop)
        thread.start()
        thread.join()
    except RuntimeError:
        # No running loop, safe to use asyncio.run
        asyncio.run(_synthesize(script, mp3_path, voice_key=voice_key))

    size_kb = mp3_path.stat().st_size // 1024
    print(f"  ✅ Audio ready: {mp3_path}  ({size_kb} KB)")

    return mp3_path


# ─────────────────────────────────────────────────────────────────────────────
# STANDALONE MODE — run directly from CLI
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate a voice note from the AI Tech Digest."
    )
    parser.add_argument(
        "--date", type=str, default=None,
        help="Digest date to read (YYYY-MM-DD). Defaults to today."
    )
    parser.add_argument(
        "--voice", type=str, default=DEFAULT_VOICE,
        help=f"Voice to use. Options: {', '.join(VOICE_OPTIONS.keys())} or a full edge-tts voice name (e.g. hi-IN-MadhurNeural). Default: {DEFAULT_VOICE}"
    )
    parser.add_argument(
        "--list-voices", action="store_true",
        help="List all available voice options and exit."
    )
    args = parser.parse_args()

    if args.list_voices:
        print("\nAvailable voices:")
        for key, name in VOICE_OPTIONS.items():
            marker = " ← default" if key == DEFAULT_VOICE else ""
            print(f"  --voice {key:<10}  →  {name}{marker}")
        sys.exit(0)

    # Resolve which digest file to read
    if args.date:
        target_date = args.date
    else:
        from zoneinfo import ZoneInfo
        ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
        target_date = f"{ist_now.strftime('%Y-%m-%d')}_{ist_now.strftime('%p')}"
    digest_file  = Path("digests") / f"digest_{target_date}_en.txt"

    if not digest_file.exists():
        print(f"\n❌ Digest file not found: {digest_file}")
        print("   Run `python3 main.py` first to generate today's digest.\n")
        sys.exit(1)

    print(f"\n🎙️  AI Tech Digest Voice Engine")
    print(f"   Date  : {target_date}")
    print(f"   Source: {digest_file}")
    print(f"   Voice : {args.voice} ({VOICE_OPTIONS[args.voice]})\n")

    output = generate_voice_note(
        digest_path=digest_file,
        voice_key=args.voice,
        date_str=target_date,
    )

    print(f"\n🎵 Play with:  open {output}")
    print(f"📤 Send to Telegram bot for testing next.\n")
