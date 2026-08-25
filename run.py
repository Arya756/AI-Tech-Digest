import threading
import time
import os
import sys
import http.server
import socketserver

# Import the main functions
from telegram_bot import run_bot
from scheduler import hourly_job

def run_scheduler():
    """Runs the scheduler loop in a separate thread.
    
    Instead of relying on the `schedule` library's timezone-dependent .at() method,
    we directly read IST time and fire at the top of every hour. This guarantees 
    delivery at exactly :00 IST regardless of the server's system timezone.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    print("🚀 Starting background scheduler thread (IST-aware)...")
    
    last_fired_hour = -1  # Tracks the last hour the job was fired to prevent double-firing
    
    while True:
        try:
            ist_now = datetime.now(ZoneInfo("Asia/Kolkata"))
            current_hour = ist_now.hour
            current_minute = ist_now.minute

            # Fire at the top of every hour (:00), but only once per hour
            if current_minute == 0 and current_hour != last_fired_hour:
                print(f"⏰ [{ist_now.strftime('%Y-%m-%d %I:%M %p IST')}] Triggering hourly job...")
                last_fired_hour = current_hour
                try:
                    hourly_job()
                except Exception as e:
                    print(f"❌ hourly_job error: {e}")
        except Exception as e:
            print(f"❌ Scheduler loop error: {e}")
        
        time.sleep(20)  # Check every 20 seconds — fine-grained enough to never miss :00

def run_health_check_server():
    """Runs a minimal HTTP server to satisfy Render's Web Service port binding check."""
    port = int(os.environ.get("PORT", 8080))
    
    class HealthHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-type", "text/plain")
            self.end_headers()
            self.wfile.write(b"AI Tech Digest Bot is fully operational!")
            
        def log_message(self, format, *args):
            # Suppress normal request logging to keep console output clean
            return

    # Allow port reuse to prevent address-already-in-use errors during redeployments
    socketserver.TCPServer.allow_reuse_address = True
    
    print(f"📡 Starting dummy HTTP health-check server on port {port}...")
    try:
        with socketserver.TCPServer(("", port), HealthHandler) as httpd:
            httpd.serve_forever()
    except Exception as e:
        print(f"⚠️ Health check server error: {e}")

if __name__ == "__main__":
    # Ensure directories exist
    os.makedirs("digests", exist_ok=True)
    
    # ── Startup self-test ────────────────────────────────────────────────
    # Fail loudly and clearly instead of running a dead service silently.
    print("🔧 Running startup self-test...")
    ok = True
    try:
        from db import client, get_subscribers_by_time
        client.admin.command("ping")
        print("  ✅ MongoDB connection OK")
    except Exception as e:
        ok = False
        print(f"  ❌ MongoDB connection FAILED: {e}")
    try:
        from telegram_bot import _check_token
        if not _check_token():
            ok = False
            print("  ❌ Telegram bot token missing/invalid")
        else:
            print("  ✅ Telegram bot token OK")
    except Exception as e:
        ok = False
        print(f"  ❌ Telegram token check FAILED: {e}")
    try:
        from db import get_subscribers_by_time
        active = get_subscribers_by_time("08:00 AM") or []
        # Count any active subscriber across all known delivery hours
        from db import subscribers_collection
        total_active = subscribers_collection.count_documents({"active": True})
        print(f"  ✅ Active subscribers in DB: {total_active}")
        if total_active == 0:
            print("  ⚠️  WARNING: zero active subscribers — scheduler will send nothing.")
    except Exception as e:
        ok = False
        print(f"  ❌ Subscriber check FAILED: {e}")

    if not ok:
        print("\n💥 Startup self-test FAILED — aborting. Fix config and redeploy.\n")
        sys.exit(1)
    print("✅ Startup self-test passed.\n")
    
    print("🌟 Starting AI Tech Digest Application...")
    
    # Start the dummy HTTP server so we can use Render's Free Web Service tier
    http_thread = threading.Thread(target=run_health_check_server, daemon=True)
    http_thread.start()
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    # Run the Telegram bot in the main thread (this blocks and keeps the app alive)
    try:
        run_bot()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")
        sys.exit(0)
