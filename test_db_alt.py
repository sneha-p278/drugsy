from pymongo import MongoClient

# URI from cerdit.txt
MONGO_URI = "mongodb+srv://swipe:medTrace@medtrace.d6fia.mongodb.net/?retryWrites=true&w=majority&appName=medTrace"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    # The ismaster command is cheap and does not require auth.
    client.admin.command('ismaster')
    print("MongoDB connection successful!")
    print(f"Databases: {client.list_database_names()}")
except Exception as e:
    print(f"Error connecting to MongoDB: {e}")
