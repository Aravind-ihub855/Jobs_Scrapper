from fastapi import FastAPI, Query
from app.simplyhired import scrape_simplyhired_jobs
from app.database import jobs_collection
from motor.motor_asyncio import AsyncIOMotorCollection
import asyncio

app = FastAPI(title="Job Scraper API")


@app.get("/scrape/simplyhired")
async def scrape_jobs(
    query: str = Query(..., example="Python Developer")
):
    # Run the synchronous blocking scraper in a threadpool to avoid blocking the async event loop
    jobs = await asyncio.to_thread(scrape_simplyhired_jobs, query)

    if jobs:
        await jobs_collection.insert_many(jobs)

    return {
        "query": query,
        "total_jobs_scraped": len(jobs),
        "status": "success"
    }
