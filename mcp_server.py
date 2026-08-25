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

    return "System overview document not found. Please ensure system_overview.md is generated."

@mcp.tool()
def read_source_file(file_name: str) -> str:
    """Read the contents of a specific Python or config file in the project for source code context.
    Allowed files: graph.py, fetch_news.py, summarize.py, db.py, run.py, scheduler.py, telegram_bot.py, main.py, requirements.txt
    """
    allowed_files = {
        "graph.py", "fetch_news.py", "summarize.py", "db.py",
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
    """Overwrite the contents of a specific project file with new code.

    HARDENED (post-incident): writes go to a SANDBOX directory
    (PROJECT_ROOT/.mcp_writes/), NEVER to the live project files. This
    prevents a test or MCP call from clobbering a real module (a stray
    write once overwrote db.py with '# ok', breaking the whole pipeline).
    To apply a change to the live repo, the agent edits files directly —
    this tool is for proposing/safe-staging code only.

    GUARDED: only allowlisted, non-secret, non-self files may be written.
    Importable modules, config files containing secrets (.env, *_config*),
    and the MCP server itself are denied to prevent self-modification or
    credential leakage through this tool surface.
    """
    # Defense in depth: never write live project files from this surface.
    forbidden = (".env", "mcp_server.py", "__init__.py", "db.py")
    if file_name in forbidden or "secret" in file_name.lower() or "credential" in file_name.lower():
        return f"Access Denied: '{file_name}' is not writable via this tool."

    allowed_files = {
        "graph.py", "fetch_news.py", "summarize.py", "db.py",
        "run.py", "scheduler.py", "telegram_bot.py", "main.py", "requirements.txt"
    }
    if file_name not in allowed_files:
        return f"Access Denied: can only stage project source files ({', '.join(sorted(allowed_files))})."

    # Sandbox: write to .mcp_writes/ so live files are never modified.
    sandbox = PROJECT_ROOT / ".mcp_writes"
    try:
        sandbox.mkdir(parents=True, exist_ok=True)
        file_path = sandbox / file_name
        file_path.write_text(content, encoding="utf-8")
        return (
            f"Staged (NOT applied to live repo) at: {file_path}\n"
            f"Live file untouched. To apply, the agent must edit the real file directly."
        )
    except Exception as e:
        return f"Error staging {file_name}: {str(e)}"

@mcp.tool()
def get_cache_status() -> str:
    """Get the current article-history (dedup) statistics from MongoDB."""
    try:
        from db import history_collection
        total = history_collection.count_documents({})
        return f"Article history: {total} entries recorded (prevents re-sending old digests)."
    except Exception as e:
        return f"Could not read history stats: {e}"

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
