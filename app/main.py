from fastapi import FastAPI, Query
from app.simplyhired import scrape_simplyhired_jobs
from app.adzuna import scrape_adzuna_jobs
from app.whatjobs import scrape_whatjobs_jobs
from app.database import simplyhired_collection, adzuna_collection, whatjobs_collection
from motor.motor_asyncio import AsyncIOMotorCollection
import asyncio

app = FastAPI(title="Job Scraper API")

@app.get("/scrape/simplyhired")
async def scrape_simplyhired(
    query: str = Query(..., example="Python Developer")
    ):
    # Run the synchronous blocking scraper in a threadpool
    jobs = await asyncio.to_thread(scrape_simplyhired_jobs, query)

    if jobs:
        await simplyhired_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            if "_id" in job:
                job["_id"] = str(job["_id"])

    return {
        "query": query,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }

@app.get("/scrape/adzuna")
async def scrape_adzuna(
    query: str = Query(..., example="Java Developer"),
    location: str = Query(None, example="US")
    ):
    # Run the synchronous blocking scraper in a threadpool
    jobs = await asyncio.to_thread(scrape_adzuna_jobs, query, location)
    
    if jobs:
        await adzuna_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            if "_id" in job:
                job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }

@app.get("/scrape/whatjobs")
async def scrape_whatjobs(
    query: str = Query(..., example="Data Scientist"),
    location: str = Query(None, example="London")
    ):
    # Run the synchronous blocking scraper in a threadpool
    jobs = await asyncio.to_thread(scrape_whatjobs_jobs, query, location)
    
    if jobs:
        await whatjobs_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            if "_id" in job:
                job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }

