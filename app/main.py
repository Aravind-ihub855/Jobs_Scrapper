import sys
import asyncio
from typing import Optional
from fastapi import FastAPI, Query
from app.simplyhired import scrape_simplyhired_jobs
from app.adzuna import scrape_adzuna_jobs
from app.monster import scrape_monster_jobs
from app.ziprecruiter import scrape_ziprecruiter_jobs
from app.database import simplyhired_collection, adzuna_collection, monster_collection, ziprecruiter_collection

# Fix for Playwright subprocesses on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

app = FastAPI(title="Job Scraper API")

@app.get("/scrape/simplyhired")
async def scrape_simplyhired(
    query: str = Query(..., example="Python Developer")
):
    jobs = await asyncio.to_thread(scrape_simplyhired_jobs, query)

    if jobs:
        await simplyhired_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
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
    jobs = await asyncio.to_thread(scrape_adzuna_jobs, query, location)

    if jobs:
        await adzuna_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }

@app.get("/scrape/monster")
async def scrape_monster(
    query: str = Query(..., example="Data Scientist"),
    location: str = Query("India", example="India")
):
    jobs = await asyncio.to_thread(scrape_monster_jobs, query, location)

    if jobs:
        await monster_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }

@app.get("/scrape/ziprecruiter")
async def scrape_ziprecruiter(
    query: str = Query(..., example="React Developer"),
    location: Optional[str] = Query(None, example="India"),
    max_pages: int = Query(1, example=1, description="Number of pages to scrape")
):
    jobs = await asyncio.to_thread(scrape_ziprecruiter_jobs, query, location, max_pages)

    if jobs:
        await ziprecruiter_collection.insert_many(jobs)
        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "status": "success",
        "data": jobs
    }
