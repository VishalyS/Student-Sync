import os
import time
import logging
from pymongo import MongoClient
import certifi
from pymongo.errors import ConnectionFailure, ServerSelectionTimeoutError
from dotenv import load_dotenv

# Load environment variables
env_path = os.path.join(os.path.dirname(__file__), '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI")

def create_mongo_client():
    """Create MongoDB client with robust connection settings"""
    if not MONGO_URI:
        raise ValueError("MONGO_URI environment variable is not set.")
    try:
        client = MongoClient(
            MONGO_URI,
            connectTimeoutMS=60000,
            socketTimeoutMS=60000,
            serverSelectionTimeoutMS=60000,
            maxPoolSize=50,
            minPoolSize=10,
            maxIdleTimeMS=45000,
            waitQueueTimeoutMS=10000,
            retryWrites=True,
            retryReads=True,
            tlsCAFile=certifi.where()
        )
        # Test the connection
        client.admin.command('ping')
        logger.info("MongoDB connection established successfully")
        return client
    except Exception as e:
        logger.error(f"Failed to create MongoDB client: {e}")
        raise

def get_database_connection():
    """Get database connection with retry logic"""
    max_retries = 3
    retry_delay = 5
    
    for attempt in range(max_retries):
        try:
            client = create_mongo_client()
            db = client['ecampus']
            return client, db
        except Exception as e:
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("All connection attempts failed")
                raise

def ensure_database_indexes(target_db):
    """Safely verify and ensure indexes on MongoDB collections without mutating data"""
    if target_db is None:
        return
    try:
        notifs_col = target_db['notifications_log']
        indexes = notifs_col.index_information()
        if "changeHash_unique" not in indexes and "changeHash_1" not in indexes:
            docs = list(notifs_col.find({"changeHash": {"$exists": True, "$ne": None}}, {"changeHash": 1}))
            hashes = [d.get("changeHash") for d in docs if d.get("changeHash")]
            from collections import Counter
            dups = [h for h, count in Counter(hashes).items() if count > 1]
            if not dups:
                notifs_col.create_index("changeHash", unique=True, sparse=True, name="changeHash_unique")
                logger.info("Verified/created unique sparse index 'changeHash_unique' on notifications_log")
            else:
                logger.warning(f"Skipped creating unique index on changeHash due to existing duplicates: {dups}")
        
        users_col = target_db['new_users']
        user_indexes = users_col.index_information()
        if "rollNo_unique" not in user_indexes and "rollNo_1" not in user_indexes:
            users_col.create_index("rollNo", unique=True, name="rollNo_unique")
            logger.info("Verified/created unique index 'rollNo_unique' on new_users")

        resets_col = target_db['password_resets']
        reset_indexes = resets_col.index_information()
        if "rollNo_1" not in reset_indexes:
            resets_col.create_index("rollNo", name="rollNo_1")
        if "expires_at_1" not in reset_indexes:
            resets_col.create_index("expires_at", name="expires_at_1")
    except Exception as e:
        logger.error(f"Error ensuring indexes on MongoDB collections: {e}")

# Initialize global database connection
try:
    client, db = get_database_connection()
    user_collection = db['new_users']
    sub_collection = db['subjects']
    notifications_collection = db['notifications_log']
    password_resets_collection = db['password_resets']
    ensure_database_indexes(db)
    logger.info("Database collections initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database: {e}")
    client, db, user_collection, sub_collection, notifications_collection, password_resets_collection = None, None, None, None, None, None