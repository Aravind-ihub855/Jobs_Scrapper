from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

simplyhired_collection = db["simplyhiredjobs"]
adzuna_collection = db["adzuna_jobs"]
monster_collection = db["monster_jobs"]
ziprecruiter_collection = db["ziprecruiter_jobs"]
