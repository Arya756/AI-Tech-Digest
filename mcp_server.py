import os
import sys
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Ensure the project root is in the Python path
PROJECT_ROOT = Path(__file__).parent.absolute()
sys.path.append(str(PROJECT_ROOT))

# Load local environment variables dynamically from .env so they are not hardcoded
from dotenv import load_dotenv
load_dotenv(dotenv_path=PROJECT_ROOT / ".env")

# Initialize FastMCP Server
mcp = FastMCP("AI News Agent Manager")

@mcp.tool()
def get_project_overview() -> str:
    """Retrieve the comprehensive system overview (architecture, features, schemas, and configurations)."""
    overview_path = PROJECT_ROOT / "system_overview.md"
    if overview_path.exists():
        return overview_path.read_text(encoding="utf-8")
    
    # Fallback to absolute conversation artifact path
    artifact_path = Path("/Users/ayusharyan/.gemini/antigravity-ide/brain/90ec91d1-4fe6-4564-940e-ca455e41895f/system_overview.md")
    if artifact_path.exists():
        return artifact_path.read_text(encoding="utf-8")
        
    return "System overview document not found. Please ensure system_overview.md is generated."

@mcp.tool()
def read_source_file(file_name: str) -> str:
    """Read the contents of a specific Python or config file in the project for source code context.
    Allowed files: graph.py, fetch_news.py, summarize.py, cache.py, db.py, run.py, scheduler.py, telegram_bot.py, main.py, requirements.txt
    """
    allowed_files = {
        "graph.py", "fetch_news.py", "summarize.py", "cache.py", "db.py",
        "run.py", "scheduler.py", "telegram_bot.py", "main.py", "requirements.txt"
    }
    if file_name not in allowed_files:
        return f"Access Denied: Can only read project source files ({', '.join(allowed_files)})"
    
    file_path = PROJECT_ROOT / file_name
    if file_path.exists():
        return f"--- {file_name} ---\n\n" + file_path.read_text(encoding="utf-8")
    return f"File {file_name} not found in project directory."

@mcp.tool()
def write_source_file(file_name: str, content: str) -> str:
    """Overwrite the contents of a specific project file with new code. Use with caution.
    Allowed files: graph.py, fetch_news.py, summarize.py, cache.py, db.py, run.py, scheduler.py, telegram_bot.py, main.py, requirements.txt
    """
    allowed_files = {
        "graph.py", "fetch_news.py", "summarize.py", "cache.py", "db.py",
        "run.py", "scheduler.py", "telegram_bot.py", "main.py", "requirements.txt"
    }
    if file_name not in allowed_files:
        return f"Access Denied: Can only write to project source files ({', '.join(allowed_files)})"
        
    file_path = PROJECT_ROOT / file_name
    try:
        file_path.write_text(content, encoding="utf-8")
        return f"Successfully updated {file_name}"
    except Exception as e:
        return f"Error writing to {file_name}: {str(e)}"

@mcp.tool()
def get_cache_status() -> str:
    """Get the current LLM cache statistics (hit/miss counts and entries)."""
    from cache import cache_stats
    return cache_stats()

@mcp.tool()
def get_latest_digest(lang: str = "en") -> str:
    """Retrieve the text of the latest generated digest from MongoDB. lang can be 'en' or 'hi'."""
    from db import digests_collection
    doc = digests_collection.find_one(
        {"lang": lang},
        sort=[("created_at", -1)]
    )
    if doc:
        return f"Latest Digest ({lang}) generated for {doc.get('date_str')}:\n\n{doc.get('content')}"
    return f"No digest found for language '{lang}'."

@mcp.tool()
def list_subscribers() -> list[dict]:
    """List all active subscribers with their chat ID, username, language, and delivery preferences."""
    from db import subscribers_collection
    subs = subscribers_collection.find({"active": True})
    result = []
    for s in subs:
        result.append({
            "chat_id": s["chat_id"],
            "username": s.get("username"),
            "language": s.get("language", "en"),
            "delivery_time": s.get("delivery_time", "08:00 AM")
        })
    return result

@mcp.tool()
def trigger_digest_generation() -> str:
    """Manually trigger today's daily digest generation (runs the full LangGraph scoring and summarization pipeline)."""
    from main import main as run_pipeline
    try:
        digest = run_pipeline()
        return f"Success! Generated digest:\n\n{digest}"
    except Exception as e:
        return f"Error running pipeline: {str(e)}"

@mcp.tool()
async def send_digest_to_subscriber(chat_id: str, date_str: str = None) -> str:
    """Send the text digest and voice briefing to a specific subscriber by chat ID. Uses optional date_str (format YYYY-MM-DD_AM/PM)."""
    from telegram_bot import send_digest
    try:
        success = await send_digest(chat_id, date_str=date_str)
        if success:
            return f"Successfully sent digest to subscriber {chat_id}"
        else:
            return f"Failed to send digest to subscriber {chat_id} (check logs)"
    except Exception as e:
        return f"Error sending digest: {str(e)}"

if __name__ == "__main__":
    mcp.run()
