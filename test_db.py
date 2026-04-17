from pymongo import MongoClient

MONGO_URI = "mongodb+srv://vpsneha719_db_user:6L0jcqgCumoS8vyi@cluster0.ricvpp8.mongodb.net/medTrace?retryWrites=true&w=majority"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # The ismaster command is cheap and does not require auth.
    client.admin.command('ismaster')
    print("MongoDB connection successful!")
    db = client["medTrace"]
    print(f"Databases: {client.list_database_names()}")
    collection = db["qrcodedata"]
    print(f"Collection count: {collection.count_documents({})}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
