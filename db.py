import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = MongoClient(MONGO_URI)
db = client["ai_news_agent"]
subscribers_collection = db["subscribers"]

def save_subscriber(chat_id: str, username: str | None = None):
    """Save a new subscriber or update existing one."""
    subscribers_collection.update_one(
        {"chat_id": str(chat_id)},
        {
            "$set":         {"chat_id": str(chat_id), "username": username, "active": True},
            "$setOnInsert": {"language": "en", "delivery_time": "08:00 AM"},  # sensible defaults for new users
        },
        upsert=True
    )
    print(f"✅ Subscriber saved to DB: {chat_id} (@{username})")

def update_preference(chat_id: str, key: str, value: str):
    """Update a specific preference (e.g., language or delivery_time)."""
    subscribers_collection.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {key: value}}
    )

def remove_subscriber(chat_id: str):
    """Mark a subscriber as inactive."""
    subscribers_collection.update_one(
        {"chat_id": str(chat_id)},
        {"$set": {"active": False}}
    )
    print(f"❌ Subscriber removed from DB: {chat_id}")

def get_subscribers_by_time(delivery_time: str) -> list[dict]:
    """Return a list of active subscribers scheduled for a specific time or its 12-hour opposite."""
    opposite_time = delivery_time.replace("AM", "PM") if "AM" in delivery_time else delivery_time.replace("PM", "AM")
    subs = subscribers_collection.find({
        "active": True, 
        "delivery_time": {"$in": [delivery_time, opposite_time]}
    })
    return [{"chat_id": sub["chat_id"], "language": sub.get("language", "en")} for sub in subs]
    
def get_subscriber(chat_id: str) -> dict | None:
    """Get a single subscriber."""
    return subscribers_collection.find_one({"chat_id": str(chat_id)})

# ─────────────────────────────────────────────────────────────────────────────
# ARTICLE HISTORY
# ─────────────────────────────────────────────────────────────────────────────
history_collection = db["history"]

def mark_article_as_sent(link: str, fingerprint: str | None = None):
    """Record an article as sent so we don't send it again on subsequent days."""
    data = {"link": link}
    if fingerprint:
        data["fingerprint"] = fingerprint
    history_collection.update_one(
        {"link": link},
        {"$set": data},
        upsert=True
    )

def is_article_sent(link: str, fingerprint: str | None = None) -> bool:
    """Check if an article has already been sent in a previous digest."""
    query = [{"link": link}]
    if fingerprint:
        query.append({"fingerprint": fingerprint})
    return history_collection.find_one({"$or": query}) is not None
