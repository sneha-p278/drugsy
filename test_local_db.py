from pymongo import MongoClient

# Testing local MongoDB
MONGO_URI = "mongodb://localhost:27017"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    client.admin.command('ismaster')
    print("Local MongoDB connection successful!")
    print(f"Databases: {client.list_database_names()}")
    db = client["medTrace"]
    collection = db["qrcodedata"]
    print(f"Collection count: {collection.count_documents({})}")
except Exception as e:
    print(f"Error connecting to local MongoDB: {e}")
