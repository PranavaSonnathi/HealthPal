from pymongo import MongoClient
import datetime
import os
client = MongoClient("mongodb://localhost:27017") 
db = client["healthpal"]
users = db["users"]
chats = db["chats"]

# --- USER AUTHENTICATION ---
def login_user(username, password):
    return users.find_one({"username": username, "password": password}) is not None

def register_user(username, password):
    if users.find_one({"username": username}):
        return False
    users.insert_one({"username": username, "password": password})
    return True

# --- CHAT STORAGE ---
def save_chat(username, session_id, mode, role, message, ocr_text=None):
    chat = {
        "username": username,
        "session_id": session_id,
        "mode": mode,
        "role": role,
        "message": message,
        "timestamp": datetime.datetime.utcnow()
    }
    if ocr_text:
        chat["ocr_text"] = ocr_text
    chats.insert_one(chat)

def get_user_history(username, limit=5):
    return list(chats.find({"username": username}).sort("timestamp", -1).limit(limit))