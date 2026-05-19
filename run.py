import threading
import time
import schedule
import os
import sys
import http.server
import socketserver

# Import the main functions
from telegram_bot import run_bot
from scheduler import hourly_job

def run_scheduler():
    """Runs the scheduler loop in a separate thread."""
    print("🚀 Starting background scheduler thread...")
    # Schedule the job to run at the start of every IST hour (which is :30 UTC)
    schedule.every().hour.at(":30").do(hourly_job)
    
    while True:
        try:
            schedule.run_pending()
        except Exception as e:
            print(f"❌ Scheduler error: {e}")
        time.sleep(30)

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
