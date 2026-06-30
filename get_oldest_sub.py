import os
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
import certifi
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where(), tlsAllowInvalidCertificates=True)
db = client["ai_news_agent"]
subscribers = db["subscribers"]

# Find the oldest subscriber by sorting by _id ascending
oldest_sub = subscribers.find_one({}, sort=[("_id", 1)])

if oldest_sub:
    print(f"OLDEST_CHAT_ID={oldest_sub['chat_id']}")
    print(f"Username: {oldest_sub.get('username')}")
else:
    print("No subscribers found.")
