import sys
import os

# Auto-activate venv if not running inside it
if not (sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import time
import asyncio
import traceback
from datetime import datetime
from pathlib import Path
from main import main as run_pipeline
from telegram_bot import send_digest
from db import get_subscribers_by_time
from utils import date_str_now

from zoneinfo import ZoneInfo

def _latest_stored_digest(lang: str) -> tuple[str, str] | None:
    """Return (date_str, content) of the most recent stored digest for `lang`,
    or None if none exists. Used as a graceful fallback when fresh generation
    fails, so subscribers still receive useful content instead of an error."""
    try:
        from db import digests_collection
        doc = digests_collection.find_one(
            {"lang": lang, "content": {"$exists": True}},
            sort=[("created_at", -1)],
        )
        if doc and doc.get("content"):
            return doc["date_str"], doc["content"]
    except Exception as e:
        print(f"⚠️ Could not query latest stored digest: {e}")
    return None

def _alert_admin(subject: str, detail: str):
    """Send a failure alert to the admin chat so errors are visible WITHOUT
    relying on Render's (paid-tier) log history. Defaults to the oldest
    subscriber chat_id if ADMIN_CHAT_ID is not set in .env."""
    import os
    admin = os.getenv("ADMIN_CHAT_ID", "").strip()
    if not admin:
        try:
            from db import subscribers_collection
            sub = subscribers_collection.find_one(sort=[("_id", 1)])
            admin = sub.get("chat_id") if sub else ""
        except Exception:
            admin = ""
    if not admin:
        print("⚠️ No admin chat_id available to alert.")
        return
    try:
        from telegram import Bot
        bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN", ""))
        msg = f"🚨 *AI Tech Digest — {subject}*\n\n```{detail[:3500]}```"
        asyncio.run(bot.send_message(chat_id=admin, text=msg, parse_mode="Markdown"))
        print(f"📨 Alert sent to admin chat {admin}")
    except Exception as e:
        print(f"⚠️ Could not send admin alert: {e}")

def ensure_digest_generated() -> str:
    """Ensure today's digest is generated (both EN and HI).

    On generation failure, falls back to the most recent stored digest so
    subscribers still get useful content. Only reports a hard failure when
    no fallback exists. Never silently drops a run.
    """
    today = date_str_now()
    txt_path_en = Path(f"digests/digest_{today}_en.txt")
    txt_path_hi = Path(f"digests/digest_{today}_hi.txt")

    # Try to restore from DB first (covers a fresh Render filesystem).
    if not txt_path_en.exists():
        try:
            from db import load_digest_text
            content = load_digest_text(today, "en")
            if content:
                txt_path_en.parent.mkdir(exist_ok=True)
                txt_path_en.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ DB load error EN: {e}")

    if not txt_path_hi.exists():
        try:
            from db import load_digest_text
            content = load_digest_text(today, "hi")
            if content:
                txt_path_hi.parent.mkdir(exist_ok=True)
                txt_path_hi.write_text(content, encoding="utf-8")
        except Exception as e:
            print(f"⚠️ DB load error HI: {e}")

    if not txt_path_en.exists() or not txt_path_hi.exists():
        print(f"\n[{datetime.now(ZoneInfo('Asia/Kolkata'))}] ⏰ Generating daily digest...")
        try:
            run_pipeline()
        except Exception as e:
            # Surface the REAL error with traceback (was previously swallowed → blind debugging).
            print(f"❌ Digest generation FAILED: {type(e).__name__}: {e}")
            tb = traceback.format_exc()
            print(tb)
            # Alert the admin directly via Telegram (no Render log history needed on free tier).
            _alert_admin("digest generation failed", f"{type(e).__name__}: {e}\n\n{tb}")
            # Graceful fallback: reuse the most recent stored digest.
            latest = _latest_stored_digest("en")
            if latest:
                date_str, content = latest
                fb_en = Path(f"digests/digest_{today}_en.txt")
                fb_en.parent.mkdir(exist_ok=True)
                fb_en.write_text(content, encoding="utf-8")
                print(f"↩️  Fell back to last stored digest ({date_str}) for EN.")
                # Hindi fallback (best-effort)
                latest_hi = _latest_stored_digest("hi")
                if latest_hi:
                    _, hi_content = latest_hi
                    fb_hi = Path(f"digests/digest_{today}_hi.txt")
                    fb_hi.write_text(hi_content, encoding="utf-8")
                    print(f"↩️  Fell back to last stored digest for HI.")
                else:
                    print("⚠️ No HI fallback available; EN-only digest will send.")
            else:
                print("💥 No fallback digest available — subscribers will get an error notice.")
                _alert_admin("no digest and no fallback",
                             f"Generation failed for {today} and no stored digest exists in MongoDB.")

    # Clean up old files to save disk space
    _cleanup_old_digests()

    return today

def _cleanup_old_digests(days: int = 7):
    """Delete digest files older than the specified number of days."""
    try:
        from db import delete_old_digests
        delete_old_digests(days)
    except Exception as e:
        print(f"⚠️ DB cleanup failed: {e}")
        
    try:
        cutoff = time.time() - (days * 86400)
        digest_dir = Path("digests")
        if not digest_dir.exists():
            return
            
        count = 0
        for f in digest_dir.iterdir():
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
                count += 1
        if count > 0:
            print(f"🧹 Cleaned up {count} old digest files.")
    except Exception as e:
        print(f"⚠️ Failed to clean up old digests: {e}")

async def send_to_time(delivery_time: str):
    subscribers = get_subscribers_by_time(delivery_time)
    if not subscribers:
        return

    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    print(f"\n[{ist_now}] 🚀 Broadcasting digest to {len(subscribers)} subscribers for {delivery_time}...")
    
    for sub in subscribers:
        chat_id = sub["chat_id"]
        try:
            success = await send_digest(chat_id)
            if success:
                print(f"✅ Successfully sent to {chat_id}")
            else:
                print(f"❌ Failed to send to {chat_id}")
        except Exception as e:
            print(f"❌ Error sending to {chat_id}: {e}")

        # Add a small delay to avoid hitting Telegram rate limits
        await asyncio.sleep(1)
        
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    print(f"[{ist_now}] 🎉 Broadcast for {delivery_time} complete!")

def hourly_job():
    from datetime import timedelta
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    # Scheduler fires at :50 so the 6-10 min pipeline completes by XX:00.
    # Look up subscribers for the NEXT hour (the one we're targeting for delivery).
    # Use timedelta so the day rolls over correctly at midnight (23:50 → 00:00 next day).
    target_dt = ist_now + timedelta(hours=1)
    target_dt = target_dt.replace(minute=0, second=0, microsecond=0)
    target_time = target_dt.strftime("%I:00 %p")
    current_time = target_time  # used downstream for log line consistency

    # Get subscribers for the target hour
    subscribers = get_subscribers_by_time(target_time)

    if not subscribers:
        # Log clearly so a "no messages sent" hour is diagnosable, not silent.
        print(f"[{ist_now}] ⏰ Hourly job for {target_time}: 0 subscribers scheduled — nothing to send.")
        return

    print(f"[{ist_now}] 📋 {len(subscribers)} subscriber(s) scheduled for {target_time}")
    ensure_digest_generated()

    # If generation failed AND no fallback digest exists, notify subscribers
    # once (don't spam every hour). Otherwise broadcast proceeds normally.
    today = date_str_now()
    if not Path(f"digests/digest_{today}_en.txt").exists():
        print(f"[{ist_now}] ❌ No digest available (generation failed, no fallback) — notifying subscribers.")
        for sub in subscribers:
            try:
                from telegram import Bot
                bot = Bot(token=os.getenv("TELEGRAM_BOT_TOKEN", ""))
                asyncio.run(bot.send_message(
                    chat_id=sub["chat_id"],
                    text=(
                        "⚠️ *AI Tech Digest — temporary issue*\n\n"
                        "We couldn't generate today's digest. We'll retry on the next "
                        "cycle. No action needed on your part."
                    ),
                    parse_mode="Markdown",
                ))
            except Exception as notify_err:
                print(f"⚠️ Could not notify {sub['chat_id']}: {notify_err}")
        return  # Cannot proceed if digest is missing

    # Pre-generating the voice notes synchronously to prevent asyncio loop crashes
    from voice_engine import generate_voice_note

    # Generate English voice note if needed
    txt_path_en = Path(f"digests/digest_{today}_en.txt")
    mp3_path_en = Path(f"digests/digest_{today}_en.mp3")
    if txt_path_en.exists() and not mp3_path_en.exists():
        try:
            from db import load_digest_mp3
            mp3_bytes = load_digest_mp3(today, "en")
            if mp3_bytes:
                mp3_path_en.write_bytes(mp3_bytes)
        except Exception as e:
            print(f"⚠️ Could not restore EN voice note from DB: {e}")

        if not mp3_path_en.exists():
            try:
                print(f"[{ist_now}] 🎙️ Pre-generating English voice note...")
                generate_voice_note(digest_path=txt_path_en, date_str=today, voice_key="ava", output_dir="digests")
                from db import save_digest_mp3
                save_digest_mp3(today, "en", mp3_path_en.read_bytes())
            except Exception as e:
                print(f"⚠️ Failed to pre-generate English audio: {e}")

    # Generate Hindi voice note if needed
    txt_path_hi = Path(f"digests/digest_{today}_hi.txt")
    mp3_path_hi = Path(f"digests/digest_{today}_hi.mp3")
    if txt_path_hi.exists() and not mp3_path_hi.exists():
        try:
            from db import load_digest_mp3
            mp3_bytes = load_digest_mp3(today, "hi")
            if mp3_bytes:
                mp3_path_hi.write_bytes(mp3_bytes)
        except Exception as e:
            print(f"⚠️ Could not restore HI voice note from DB: {e}")

        if not mp3_path_hi.exists():
            try:
                print(f"[{ist_now}] 🎙️ Pre-generating Hindi voice note...")
                generate_voice_note(digest_path=txt_path_hi, date_str=today, voice_key="hi-IN-MadhurNeural", output_dir="digests")
                from db import save_digest_mp3
                save_digest_mp3(today, "hi", mp3_path_hi.read_bytes())
            except Exception as e:
                print(f"⚠️ Failed to pre-generate Hindi audio: {e}")

    # Broadcast the result
    asyncio.run(send_to_time(current_time))
