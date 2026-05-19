import sys
import os

# Auto-activate venv if not running inside it
if not (sys.base_prefix != sys.prefix):
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python3")
    if os.path.exists(venv_python):
        os.execv(venv_python, [venv_python] + sys.argv)

import schedule
import time
import asyncio
from datetime import datetime
from pathlib import Path
from main import main as run_pipeline
from telegram_bot import send_digest
from db import get_subscribers_by_time

from zoneinfo import ZoneInfo

def ensure_digest_generated():
    """Ensure today's digest is generated (both EN and HI)."""
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = ist_now.strftime("%Y-%m-%d")
    txt_path_en = Path(f"digests/digest_{today}_en.txt")
    txt_path_hi = Path(f"digests/digest_{today}_hi.txt")
    
    if not txt_path_en.exists() or not txt_path_hi.exists():
        print(f"\n[{ist_now}] ⏰ Generating daily digest...")
        run_pipeline()
        
    # Clean up old files to save disk space
    _cleanup_old_digests()
    
    return today

def _cleanup_old_digests(days: int = 7):
    """Delete digest files older than the specified number of days."""
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
    ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
    current_time = ist_now.strftime("%I:00 %p")  # "07:00 AM", "08:00 AM" etc.
    
    # Get subscribers for this hour
    subscribers = get_subscribers_by_time(current_time)
    
    if subscribers:
        try:
            ensure_digest_generated()
        except Exception as e:
            print(f"❌ Failed to generate digest: {e}")
            return # Cannot proceed if digest is missing
            
        # Pre-generating the voice notes synchronously to prevent asyncio loop crashes
        today = ist_now.strftime("%Y-%m-%d")
        from voice_engine import generate_voice_note
        
        # Generate English voice note if needed
        txt_path_en = Path(f"digests/digest_{today}_en.txt")
        mp3_path_en = Path(f"digests/digest_{today}_en.mp3")
        if txt_path_en.exists() and not mp3_path_en.exists():
            try:
                print(f"[{ist_now}] 🎙️ Pre-generating English voice note...")
                generate_voice_note(digest_path=txt_path_en, date_str=today, voice_key="ava", output_dir="digests")
            except Exception as e:
                print(f"⚠️ Failed to pre-generate English audio: {e}")
                
        # Generate Hindi voice note if needed
        txt_path_hi = Path(f"digests/digest_{today}_hi.txt")
        mp3_path_hi = Path(f"digests/digest_{today}_hi.mp3")
        if txt_path_hi.exists() and not mp3_path_hi.exists():
            try:
                print(f"[{ist_now}] 🎙️ Pre-generating Hindi voice note...")
                generate_voice_note(digest_path=txt_path_hi, date_str=today, voice_key="hi-IN-MadhurNeural", output_dir="digests")
            except Exception as e:
                print(f"⚠️ Failed to pre-generate Hindi audio: {e}")
        
        # Broadcast the result
        asyncio.run(send_to_time(current_time))

if __name__ == "__main__":
    print("🚀 Hourly Scheduler started! Waiting for delivery windows...")
    
    # Schedule the job to run at the start of every IST hour (which is :30 UTC)
    schedule.every().hour.at(":30").do(hourly_job)
    
    # For testing purposes:
    # hourly_job()
    
    while True:
        schedule.run_pending()
        time.sleep(60)
