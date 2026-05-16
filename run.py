import threading
import time
import schedule
import os
import sys

# Import the main functions
from telegram_bot import run_bot
from scheduler import hourly_job

def run_scheduler():
    """Runs the scheduler loop in a separate thread."""
    print("🚀 Starting background scheduler thread...")
    # Schedule the job to run at the start of every hour
    schedule.every().hour.at(":00").do(hourly_job)
    
    while True:
        schedule.run_pending()
        time.sleep(30)

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs("digests", exist_ok=True)
    
    print("🌟 Starting AI Tech Digest Application...")
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Run the Telegram bot in the main thread (this blocks and keeps the app alive)
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        sys.exit(0)
