#!/usr/bin/env python3
"""Telegram connector for the AI Tech Digest Agent.

Two modes:
  1. SEND mode  — send today's digest (text + voice note) to a chat_id
  2. BOT mode   — run an interactive bot that lets users subscribe via /start

Usage:
  python3 telegram_bot.py --send            # send to TELEGRAM_CHAT_ID in .env
  python3 telegram_bot.py --send --chat-id 123456789   # override chat_id
  python3 telegram_bot.py --bot             # run interactive subscription bot
  python3 telegram_bot.py --test            # send a short test message only
"""
import sys
import os

# Auto-activate venv if not running inside it
if not (sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import os
import sys
import asyncio
import argparse
from datetime import date  # kept for any legacy references
from pathlib import Path

from dotenv import load_dotenv
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, Update, InputMediaPhoto
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────────────────────────────────────

BOT_TOKEN   = os.getenv("TELEGRAM_BOT_TOKEN", "")
DEFAULT_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

DIGESTS_DIR = Path("digests")
BOT_NAME    = "AI Tech Digest"
BOT_TAGLINE = "Your daily 3-minute AI briefing. Read less, know more. 🎙️"


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _today() -> str:
    from utils import date_str_now
    return date_str_now()


def _digest_txt(date_str: str, lang: str = "en") -> Path:
    return DIGESTS_DIR / f"digest_{date_str}_{lang}.txt"


def _digest_mp3(date_str: str, lang: str = "en") -> Path:
    return DIGESTS_DIR / f"digest_{date_str}_{lang}.mp3"


def _check_token() -> bool:
    if not BOT_TOKEN:
        print("\n❌  TELEGRAM_BOT_TOKEN is not set in your .env file.")
        print("    Steps to get one:")
        print("    1. Open Telegram and message @BotFather")
        print("    2. Send /newbot and follow the prompts")
        print("    3. Copy the token and add it to .env:")
        print("       TELEGRAM_BOT_TOKEN=your_token_here\n")
        return False
    return True


def _parse_digest_articles(digest_path: Path) -> list[dict]:
    """
    Parse the digest .txt file into a list of article dicts for formatting.
    Returns list of {title, summary, context, impact, source, link, priority}.
    """
    import re
    raw = digest_path.read_text(encoding="utf-8")
    articles = []

    story_blocks = re.split(r"(?m)^\d+\.", raw)

    for block in story_blocks[1:]:
        title    = ""
        source   = ""
        summary  = ""
        context  = ""   # 🧠 background field
        impact   = ""
        link     = ""
        priority = "📰"
        audience = ""   # 👥 derived from category, zero LLM cost
        category = ""   # 🏷️ category (lowercased), e.g. "research"

        for raw_line in block.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            # Priority tag from the first line (contains 🔥 or ⚡ or 📌)
            if "🔥" in line:
                priority = "🔥"
            elif "⚡" in line:
                priority = "⚡"
            elif "📌" in line:
                priority = "📌"

            # Title line — 📰
            if "\U0001F4F0" in line and not title:
                title = re.sub(r"^\U0001F4F0\s*", "", line).strip()

            # Category/Source line — 🏷️ / 📡  (format: "CATEGORY | 📡 Source")
            elif "\U0001F3F7" in line or "\U0001F4E1" in line:
                if "|" in line:
                    cat_raw = line.split("|")[0]
                    category = re.sub(r"[^A-Za-z]", " ", cat_raw).strip().lower()
                    source_raw = line.split("|")[-1].strip()
                    source = re.sub(r"[\U0001F4E1\s]+", " ", source_raw).strip()

            # Summary — 📝
            elif "\U0001F4DD" in line and not summary:
                summary = re.sub(r"^\U0001F4DD\s*", "", line).strip()

            # Context — 🧠  ← THE MISSING HANDLER
            elif "\U0001F9E0" in line and not context:
                context = re.sub(r"^\U0001F9E0\s*", "", line).strip()

            # Why it matters — 👉
            elif "\U0001F449" in line and not impact:
                impact = re.sub(r"^\U0001F449\s*", "", line).strip()

            # Audience — 👥
            elif "\U0001F465" in line and not audience:
                audience = re.sub(r"^\U0001F465\s*", "", line).strip()

            # Link — 🔗
            elif "\U0001F517" in line or line.startswith("http"):
                link = re.sub(r"^\U0001F517\s*", "", line).strip()

        # Fallback guard — if audience tag is missing (e.g. format drift after a
        # summarize.py change), default gracefully instead of silently dropping the tag.
        if not audience:
            audience = "🌐 Everyone"
            if title:  # only warn when we actually parsed a real story block
                print(f"⚠️  Parser: missing audience tag for '{title[:50]}' — check .txt format")

        if title:
            articles.append({
                "title":    title,
                "source":   source,
                "summary":  summary,
                "context":  context,
                "impact":   impact,
                "link":     link,
                "priority": priority,
                "audience": audience,
                "category": category,
            })

    return articles


def _format_telegram_message(articles: list[dict], date_str: str) -> tuple[str, InlineKeyboardMarkup | None]:
    """
    Build the Telegram-formatted message and inline keyboard buttons.
    Uses Telegram's MarkdownV2 (special chars must be escaped).
    """
    import re

    def esc(text: str) -> str:
        """Escape special chars for MarkdownV2 (delegates to shared helper)."""
        from utils import esc as _esc_fn
        return _esc_fn(text)

    today_display = date.today().strftime("%B %d, %Y")
    clean_tagline = BOT_TAGLINE.replace("🎙️", "").strip()
    lines = [
        f"*AI Tech Digest — {esc(today_display)}*",
        f"_{esc(clean_tagline)}_",
        "",
    ]

    buttons = []

    for i, art in enumerate(articles, 1):
        priority = art["priority"]
        title    = esc(art["title"])
        summary  = esc(art["summary"]) if art["summary"] else ""
        source   = esc(art["source"]) if art["source"] else ""
        impact   = esc(art["impact"]) if art["impact"] else ""
        context  = esc(art.get("context", "")) if art.get("context") else ""
        audience = esc(art.get("audience", ""))

        lines.append(f"*{i}\\. {title}*")
        lines.append("")
        if audience:
            lines.append(f"_{audience}_")
            lines.append("")
        if source:
            lines.append(f"\u2022 *Source:* _{source}_")
            lines.append("")
        if summary:
            lines.append(f"\u2022 *Summary:* {summary}")
            lines.append("")
        if context:
            lines.append(f"\u2022 *Context:* {context}")
            lines.append("")
        if impact:
            lines.append(f"\u2022 *Impact:* {impact}")
        # Visual divider between stories (except after last)
        if i < len(articles):
            lines.append("―――――――――――――")
        lines.append("")

        if art.get("link"):
            buttons.append([
                InlineKeyboardButton(
                    f"{i}. {art['title'][:45]}...",
                    url=art["link"]
                )
            ])

    lines.append("─────────────────────────")
    lines.append("_Voice note below_")

    keyboard = InlineKeyboardMarkup(buttons) if buttons else None
    return "\n".join(lines), keyboard


# ─────────────────────────────────────────────────────────────────────────────
# THUMBNAIL GALLERY
# ─────────────────────────────────────────────────────────────────────────────

def _build_thumb_items(articles: list[dict], date_str: str, lang: str) -> list[dict]:
    """
    Return structured item dicts (title/source/category/total_score/link) for
    thumbnail rendering. Prefer persisted structured items from the DB (they
    carry the REAL category + score from ranking); fall back to the parsed
    text digest, using the article's own category field when present.
    """
    try:
        from db import load_digest_items
        items = load_digest_items(date_str, lang)
        if items:
            return items
    except Exception as e:
        print(f"⚠️ load_digest_items failed ({e}) — falling back to parsed text")

    # Fallback: derive from parsed text articles. Use the article's own
    # category (e.g. "RESEARCH") when available; otherwise infer from priority.
    prio_score = {"🔥 CRITICAL": 20.0, "⚡ IMPORTANT": 15.0, "📌 NOTE": 9.0}
    cat_map = {"🔥": "ai", "⚡": "ai_tools", "📌": "other"}
    out = []
    for art in articles:
        pri = art.get("priority", "")
        # Prefer a real category parsed from the 🏷️ line, else infer from priority.
        # Normalize (spaces -> underscores) so "ai tools" matches the palette key.
        raw_cat = art.get("category") or cat_map.get(pri, "other")
        cat = str(raw_cat).strip().lower().replace(" ", "_")
        score = art.get("total_score") or prio_score.get(pri, 10.0)
        out.append({
            "title": art.get("title", "Untitled"),
            "source": art.get("source", ""),
            "category": cat,
            "total_score": score,
            "link": art.get("link", ""),
            "summary": art.get("summary", ""),
            "context": art.get("context", ""),
        })
    return out


def _render_thumbnails(items: list[dict], date_str: str, lang: str) -> list[tuple[str, dict]]:
    """
    Render one PNG per story via thumbnail.py. Returns [(png_path, item)].
    Failures are skipped individually (never abort the whole gallery).
    """
    from thumbnail import generate_story_thumbnail
    results = []
    for i, it in enumerate(items, 1):
        it = dict(it)
        it["_date_str"] = date_str
        try:
            p = generate_story_thumbnail(it, i, lang=lang)
            results.append((p, it))
        except Exception as e:
            print(f"  ⚠️ Thumbnail render failed for story {i}: {e}")
    return results


# ─────────────────────────────────────────────────────────────────────────────
# SEND FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

async def send_digest(chat_id: str, date_str: str | None = None) -> bool:
    """
    Send the text digest + voice note to a Telegram chat.
    Returns True on success.
    """
    from db import get_subscriber
    user = get_subscriber(chat_id)
    lang = user.get("language", "en") if user else "en"
    
    date_str   = date_str or _today()
    txt_path   = _digest_txt(date_str, lang=lang)
    mp3_path   = _digest_mp3(date_str, lang=lang)

    if not txt_path.exists():
        try:
            from db import load_digest_text
            content = load_digest_text(date_str, lang)
            if content:
                txt_path.parent.mkdir(exist_ok=True)
                txt_path.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ DB load error for text: {e}")
            
    if not txt_path.exists():
        print(f"❌  Digest text not found: {txt_path}")
        print("    Run `python3 main.py` first.")
        return False

    if not mp3_path.exists():
        try:
            from db import load_digest_mp3
            mp3_bytes = load_digest_mp3(date_str, lang)
            if mp3_bytes:
                mp3_path.write_bytes(mp3_bytes)
        except Exception as e:
            print(f"⚠️ DB load error for mp3: {e}")

    if not mp3_path.exists():
        print(f"⚠️   Voice note not found: {mp3_path}")
        print("    Generating now...")
        from voice_engine import generate_voice_note
        voice_key = "hi-IN-MadhurNeural" if lang == "hi" else "ava"
        import asyncio
        await asyncio.to_thread(
            generate_voice_note,
            articles=None,
            digest_path=txt_path,
            output_dir="digests",
            voice_key=voice_key,
            date_str=date_str,
            lang=lang,
        )

    bot      = Bot(token=BOT_TOKEN)
    articles = _parse_digest_articles(txt_path)

    if not articles:
        print("❌  No articles parsed from digest. Check the digest file format.")
        return False

    text_msg, keyboard = _format_telegram_message(articles, date_str)

    print(f"\n📤 Sending digest to chat_id: {chat_id}")

    # 1. Send the full formatted text briefing (web previews off → clean)
    print("  → Sending text message...")
    await bot.send_message(
        chat_id    = chat_id,
        text       = text_msg,
        parse_mode = ParseMode.MARKDOWN_V2,
        reply_markup = keyboard,
        disable_web_page_preview = True,
    )
    print("  ✅ Text sent")

    # 1.5 Send a SEQUENTIAL per-story gallery: thumbnail photo, then a short
    # text block with a tappable "Read" link — repeated for each story, so the
    # chat reads: thumb → text+link → thumb → text+link ... then voice at end.
    # Guarded: a thumbnail/parse failure must never block text/voice delivery.
    try:
        from utils import esc as _esc
        thumb_items = _build_thumb_items(articles, date_str, lang)
        rendered = _render_thumbnails(thumb_items, date_str, lang)
        for idx, (png_path, it) in enumerate(rendered, 1):
            # Photo first
            try:
                with open(png_path, "rb") as photo:
                    await bot.send_photo(chat_id=chat_id, photo=photo)
            except Exception as pe:
                print(f"  ⚠️ Thumbnail {idx} send failed: {pe}")
                continue
            # Then the text + tappable Read link (preview off → no auto cards)
            title_esc = _esc(it.get("title", "")[:80])
            src_esc   = _esc(it.get("source", ""))
            sum_esc   = _esc(it.get("summary", "")[:300])
            ctx_esc   = _esc(it.get("context", "")[:200])
            link      = it.get("link", "")
            cap = f"*{idx}\\. {title_esc}*"
            if src_esc:
                cap += f"\n_{src_esc}_"
            if sum_esc:
                cap += f"\n\n{sum_esc}"
            elif ctx_esc:
                cap += f"\n\n{ctx_esc}"
            cap += f"\n\n🔗 [Read full story]({link})"
            await bot.send_message(
                chat_id = chat_id,
                text = cap,
                parse_mode = ParseMode.MARKDOWN_V2,
                disable_web_page_preview = True,
            )
        print(f"  ✅ Sequential gallery sent ({len(rendered)} stories)")
    except Exception as e:
        print(f"  ⚠️ Gallery send failed (text/voice still delivered): {e}")

    # 2. Send the voice note
    print("  → Uploading voice note...")
    with open(mp3_path, "rb") as audio_file:
        await bot.send_audio(
            chat_id       = chat_id,
            audio         = audio_file,
            title         = f"AI Tech Digest — {date_str}",
            performer     = "AI Tech Digest",
            caption       = "🎙️ Listen to today's full briefing",
            read_timeout  = 60,
            write_timeout = 60,
            connect_timeout = 60
        )
    print("  ✅ Voice note sent")
    return True


async def send_test_message(chat_id: str) -> None:
    """Send a quick test message to verify the bot token and chat_id work."""
    bot = Bot(token=BOT_TOKEN)
    await bot.send_message(
        chat_id = chat_id,
        text    = (
            "✅ *AI Tech Digest Bot is connected\\!*\n\n"
            "Your daily AI briefing will be delivered here every morning\\.\n"
            "Use /start to manage your subscription\\."
        ),
        parse_mode = ParseMode.MARKDOWN_V2,
    )
    print(f"\n✅ Test message sent to {chat_id}")
    print("   Check your Telegram app!\n")


# ─────────────────────────────────────────────────────────────────────────────
# INTERACTIVE BOT — handles /start, /stop, /help commands
# ─────────────────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start — welcome new subscribers and ask for language."""
    if not update.effective_user or not update.effective_chat or not update.message:
        return
    user    = update.effective_user
    chat_id = update.effective_chat.id

    display_name = user.username or user.first_name
    print(f"  👋 New subscriber: {display_name} ({chat_id})")

    # Save initial subscriber with default active status
    from db import save_subscriber
    save_subscriber(chat_id=str(chat_id), username=display_name)

    keyboard = [
        [
            InlineKeyboardButton("English 🇬🇧", callback_data="lang_en"),
            InlineKeyboardButton("Hindi 🇮🇳", callback_data="lang_hi"),
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # Use basic MARKDOWN so we don't have to escape standard characters
    await update.message.reply_text(
        f"👋 Hey {user.first_name}! Welcome to *AI Tech Digest*.\n\n"
        f"Every morning you'll get curated AI stories and a voice briefing.\n\n"
        f"First, please choose your preferred language:",
        reply_markup=reply_markup,
        parse_mode=ParseMode.MARKDOWN,
    )

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.callback_query or not update.effective_chat:
        return
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    data = query.data or ""

    from db import update_preference

    if data.startswith("lang_"):
        lang = data.split("_")[1]
        update_preference(chat_id, "language", lang)
        
        # Now ask for time
        keyboard = [
            [
                InlineKeyboardButton("07:00 AM", callback_data="time_07:00 AM"),
                InlineKeyboardButton("08:00 AM", callback_data="time_08:00 AM"),
                InlineKeyboardButton("09:00 AM", callback_data="time_09:00 AM"),
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            text=f"Language set to {'English' if lang == 'en' else 'Hindi'}. Now, choose your daily delivery time:",
            reply_markup=reply_markup
        )
        
    elif data.startswith("time_"):
        time = data[len("time_"):]  # prefix strip — safe even if value contains underscores
        update_preference(chat_id, "delivery_time", time)

        # Calculate the PM counterpart so users know about the evening edition
        pm_time = time.replace("AM", "PM")
        await query.edit_message_text(
            text=(
                f"✅ All set! You will receive your AI Tech Digest twice daily:\n\n"
                f"🌅 Morning: {time}\n"
                f"🌆 Evening: {pm_time}\n\n"
                f"Each edition brings fresh, non-repeating stories!"
            )
        )


async def cmd_stop(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /stop — unsubscribe."""
    if not update.message or not update.effective_chat:
        return
    # Use plain text to avoid MarkdownV2 escaping issues with apostrophes
    await update.message.reply_text(
        "😢 You've been unsubscribed. You won't receive any more digests.\n"
        "Send /start anytime to resubscribe."
    )
    from db import remove_subscriber
    remove_subscriber(chat_id=str(update.effective_chat.id))


async def cmd_latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /latest — send today's digest on demand."""
    if not update.message or not update.effective_chat:
        return
    chat_id = str(update.effective_chat.id)
    
    await update.message.reply_text("⏳ Fetching today's digest... (Might take a minute if generating fresh)")
    
    import asyncio
    from scheduler import ensure_digest_generated
    try:
        await asyncio.to_thread(ensure_digest_generated)
    except Exception as e:
        print(f"❌ Error generating digest on demand: {e}")

    success = await send_digest(chat_id)
    if not success:
        await update.message.reply_text(
            "⚠️ No digest available yet\\. Try again after 9 AM\\.",
            parse_mode=ParseMode.MARKDOWN_V2,
        )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(
        "*AI Tech Digest — Help*\n\n"
        "/start — subscribe to daily digest\n"
        "/stop — unsubscribe\n"
        "/latest — get today's digest right now\n"
        "/help — show this message",
        parse_mode=ParseMode.MARKDOWN_V2,
    )


def run_bot() -> None:
    """Run the interactive Telegram bot (blocking)."""
    print(f"\n🤖 Starting {BOT_NAME} bot...")
    print("   Press Ctrl+C to stop.\n")

    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(CommandHandler("stop",   cmd_stop))
    app.add_handler(CommandHandler("latest", cmd_latest))
    app.add_handler(CommandHandler("help",   cmd_help))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


# ─────────────────────────────────────────────────────────────────────────────
# CLI ENTRY POINT
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AI Tech Digest Telegram connector.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--send",  action="store_true", help="Send today's digest.")
    group.add_argument("--bot",   action="store_true", help="Run interactive subscription bot.")
    group.add_argument("--test",  action="store_true", help="Send a test message only.")

    parser.add_argument("--chat-id", type=str, default=DEFAULT_CHAT,
                        help="Override the target chat_id.")
    parser.add_argument("--date", type=str, default=None,
                        help="Send a specific date's digest (YYYY-MM-DD).")
    args = parser.parse_args()

    if not _check_token():
        sys.exit(1)

    if args.bot:
        run_bot()

    elif args.test:
        if not args.chat_id:
            print("\n❌  Provide --chat-id or set TELEGRAM_CHAT_ID in .env")
            print("    To find your chat_id:")
            print("    1. Message your bot on Telegram")
            print("    2. Visit: https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates")
            print("    3. Look for 'chat': {'id': 123456789}")
            sys.exit(1)
        asyncio.run(send_test_message(args.chat_id))

    elif args.send:
        if not args.chat_id:
            print("\n❌  Provide --chat-id or set TELEGRAM_CHAT_ID in .env")
            sys.exit(1)
        success = asyncio.run(send_digest(args.chat_id, date_str=args.date))
        sys.exit(0 if success else 1)
