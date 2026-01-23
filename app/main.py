import sys
from fastapi import FastAPI, Query
from typing import Optional
from app.simplyhired import scrape_simplyhired_jobs
from app.adzuna import scrape_adzuna_jobs
from app.whatjobs import scrape_whatjobs_jobs
from app.naukri import scrape_naukri_jobs
from app.ziprecruiter import scrape_ziprecruiter_jobs
from app.monster import scrape_monster_jobs
from app.leetcode import scrape_leetcode_questions
from app.database import simplyhired_collection, adzuna_collection, whatjobs_collection, naukri_collection, ziprecruiter_collection, monster_collection, leetcode_collection
from motor.motor_asyncio import AsyncIOMotorCollection
import asyncio
from concurrent.futures import ProcessPoolExecutor

app = FastAPI(title="Job Scraper API")

# Fix for Playwright subprocesses on Windows
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

executor = ProcessPoolExecutor(max_workers=2)


@app.get("/scrape/simplyhired")
async def scrape_simplyhired(
    query: str = Query(..., example="Python Developer")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, scrape_simplyhired_jobs, query)

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
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, scrape_adzuna_jobs, query, location)
    
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

@app.get("/scrape/whatjobs")
async def scrape_whatjobs(
    query: str = Query(..., example="Data Scientist"),
    location: str = Query(None, example="London")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, scrape_whatjobs_jobs, query, location)
    
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

@app.get("/scrape/naukri")
async def scrape_naukri(
    query: str = Query(..., example="Data Engineer Intern"),
    location: str = Query(None, example="Bengaluru")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, scrape_naukri_jobs, query, location)
    
    if jobs:
        await naukri_collection.insert_many(jobs)
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

@app.get("/scrape/leetcode")
async def scrape_leetcode(
    query: str = Query(..., example="iterator")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(executor, scrape_leetcode_questions, query)
    
    if questions:
        await leetcode_collection.insert_many(questions)
        # Convert ObjectId to string for JSON serialization
        for q in questions:
            if "_id" in q:
                q["_id"] = str(q["_id"])

    return {
        "query": query,
        "total_questions_scraped": len(questions),
        "status": "success",
        "data": questions
    }

