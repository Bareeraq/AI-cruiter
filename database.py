# database.py
from pymongo import MongoClient
import logging
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv(dotenv_path="./config/.env")

# MongoDB setup using environment variables
MONGO_URI = os.getenv("MONGO_URI")
DATABASE_NAME = os.getenv("DATABASE_NAME")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "Ai-cruiter")  # Default to "resumes" if not specified

if not MONGO_URI or not DATABASE_NAME:
    raise ValueError("MONGO_URI and DATABASE_NAME must be set in the .env file.")

# Initialize MongoDB client and database
client = MongoClient(MONGO_URI)
db = client[DATABASE_NAME]
collection = db[COLLECTION_NAME]

def save_to_mongo_db(data):
    """
    Save data to the MongoDB collection.
    :param data: Dictionary containing data to save.
    """
    try:
        # Insert data into the MongoDB collection
        result = collection.insert_one(data)
        logging.info(f"Inserted document with ID: {result.inserted_id}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error saving to MongoDB: {e}")
        raise
