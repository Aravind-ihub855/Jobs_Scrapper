from fastapi import FastAPI, Query
from app.simplyhired import scrape_simplyhired_jobs
from app.adzuna import scrape_adzuna_jobs
from app.database import simplyhired_collection, adzuna_collection
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

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }
