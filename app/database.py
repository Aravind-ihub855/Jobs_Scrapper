from motor.motor_asyncio import AsyncIOMotorClient
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

simplyhired_collection = db["simplyhired_jobs"]
adzuna_collection = db["adzuna_jobs"]
whatjobs_collection = db["whatjobs_jobs"]
naukri_collection = db["naukri_jobs"]
monster_collection = db["monster_jobs"]
ziprecruiter_collection = db["ziprecruiter_jobs"]
leetcode_collection = db["leetcode_questions"]
gfg_collection = db["gfg_questions"]
exercism_collection = db["exercism_exercises"]
hackerrank_collection = db["hackerrank_challenges"]
codechef_collection = db["codechef_problems"]