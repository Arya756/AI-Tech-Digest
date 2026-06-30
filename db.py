import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
import certifi
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
db = client["ai_news_agent"]
subscribers_collection = db["subscribers"]

def save_subscriber(chat_id: str, username: str | None = None):
    """Save a new subscriber or update existing one."""
    subscribers_collection.update_one(
        {"chat_id": chat_id},
        {
            "$set":         {"chat_id": chat_id, "username": username, "active": True},
            "$setOnInsert": {"language": "en", "delivery_time": "08:00 AM"},  # sensible defaults for new users
        },
        upsert=True
    )
    print(f"✅ Subscriber saved to DB: {chat_id} (@{username})")

def update_preference(chat_id: str, key: str, value: str):
    """Update a specific preference (e.g., language or delivery_time)."""
    subscribers_collection.update_one(
        {"chat_id": chat_id},
        {"$set": {key: value}}
    )

def remove_subscriber(chat_id: str):
    """Mark a subscriber as inactive."""
    subscribers_collection.update_one(
        {"chat_id": chat_id},
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
    return subscribers_collection.find_one({"chat_id": chat_id})

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

# ─────────────────────────────────────────────────────────────────────────────
# DIGEST PERSISTENCE (GridFS + Documents)
# ─────────────────────────────────────────────────────────────────────────────
import gridfs
import time

digests_collection = db["daily_digests"]
fs = gridfs.GridFS(db, collection="digest_audio")

def save_digest_text(date_str: str, lang: str, content: str):
    """Save the text digest into MongoDB."""
    digests_collection.update_one(
        {"date_str": date_str, "lang": lang},
        {
            "$set": {
                "date_str": date_str,
                "lang": lang,
                "content": content,
                "created_at": time.time()
            }
        },
        upsert=True
    )
    print(f"✅ Text digest saved to DB: {date_str} ({lang})")

def load_digest_text(date_str: str, lang: str) -> str | None:
    """Load the text digest from MongoDB."""
    doc = digests_collection.find_one({"date_str": date_str, "lang": lang})
    return doc["content"] if doc else None

def save_digest_mp3(date_str: str, lang: str, mp3_bytes: bytes):
    """Save the MP3 voice note into MongoDB via GridFS."""
    filename = f"digest_{date_str}_{lang}.mp3"
    
    # Delete old file with same name if it exists (GridFS doesn't upsert directly)
    existing = fs.find_one({"filename": filename})
    if existing:
        fs.delete(existing._id)
        
    fs.put(mp3_bytes, filename=filename, created_at=time.time())
    print(f"✅ MP3 digest saved to DB: {filename}")

def load_digest_mp3(date_str: str, lang: str) -> bytes | None:
    """Load the MP3 voice note from MongoDB via GridFS."""
    filename = f"digest_{date_str}_{lang}.mp3"
    doc = fs.find_one({"filename": filename})
    return doc.read() if doc else None

def delete_old_digests(days: int = 7):
    """Delete digests and MP3s older than the specified number of days."""
    cutoff = time.time() - (days * 86400)
    
    # Delete from text collection
    res = digests_collection.delete_many({"created_at": {"$lt": cutoff}})
    
    # Delete from GridFS
    count = 0
    for file in fs.find({"created_at": {"$lt": cutoff}}):
        fs.delete(file._id)
        count += 1
        
    if res.deleted_count > 0 or count > 0:
        print(f"🧹 Cleaned up DB: {res.deleted_count} texts, {count} MP3s deleted.")
