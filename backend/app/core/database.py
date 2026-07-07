from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient
from app.core.config import settings
from typing import Optional


class MongoDB:
    client: Optional[AsyncIOMotorClient] = None
    sync_client: Optional[MongoClient] = None


mongodb = MongoDB()


async def connect_to_mongo():
    try:
        mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        mongodb.sync_client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        await mongodb.client.admin.command('ping')
        print("Connected to MongoDB")
    except Exception as e:
        print(f"Warning: Could not connect to MongoDB at {settings.MONGODB_URL}")
        print(f"Error: {str(e)}")
        print("Server will continue but database operations may fail.")
        mongodb.client = None
        mongodb.sync_client = None


async def close_mongo_connection():
    if mongodb.client:
        mongodb.client.close()
    if mongodb.sync_client:
        mongodb.sync_client.close()


def get_database():
    if mongodb.client is None:
        try:
            mongodb.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
            mongodb.sync_client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        except Exception as e:
            print(f"Error creating MongoDB connection: {str(e)}")
            raise
    return mongodb.client[settings.MONGODB_DB_NAME]


def get_sync_database():
    if mongodb.sync_client is None:
        try:
            mongodb.sync_client = MongoClient(settings.MONGODB_URL, serverSelectionTimeoutMS=5000)
        except Exception as e:
            print(f"Error creating MongoDB sync connection: {str(e)}")
            raise
    return mongodb.sync_client[settings.MONGODB_DB_NAME]


def get_db():
    return get_database()
