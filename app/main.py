import sys
from fastapi import FastAPI, Query
from typing import Optional, List
from app.simplyhired import scrape_simplyhired_jobs
from app.adzuna import scrape_adzuna_jobs
from app.whatjobs import scrape_whatjobs_jobs
from app.naukri import scrape_naukri_jobs
from app.ziprecruiter import scrape_ziprecruiter_jobs
from app.monster import scrape_monster_jobs
from app.leetcode import scrape_leetcode_questions
from app.geeksforgeeks import scrape_gfg_questions
from app.exercism import scrape_exercism_questions
from app.hackerrank import scrape_hackerrank_questions
from app.codechef import scrape_codechef_questions
from app.prepinsta import scrape_prepinsta_questions
from app.interviewbit import scrape_interviewbit_questions
from app.database import simplyhired_collection, adzuna_collection, whatjobs_collection, naukri_collection, ziprecruiter_collection, monster_collection, leetcode_collection, gfg_collection, exercism_collection, hackerrank_collection,codechef_collection,prepinsta_collection, interviewbit_collection
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
    location: str = Query(None, example="London"),
    pages: int = Query(2, example=2, description="Number of pages to scrape")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    jobs = await loop.run_in_executor(executor, scrape_whatjobs_jobs, query, location, pages)
    
    saved_count = 0
    if jobs:
        # Use upsert to avoid duplicates based on job_url
        for job in jobs:
            if "job_url" in job and job["job_url"]:
                result = await whatjobs_collection.update_one(
                    {"job_url": job["job_url"]},
                    {"$set": job},
                    upsert=True
                )
                if result.upserted_id or result.modified_count > 0:
                    saved_count += 1
            else:
                # If no URL, just insert (less ideal but safe)
                await whatjobs_collection.insert_one(job)
                saved_count += 1

        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            if "_id" in job:
                job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "new_or_updated_jobs": saved_count,
        "status": "success",
        "data": jobs
    }

@app.get("/scrape/naukri")
async def scrape_naukri(
    query: str = Query(..., example="Data Engineer Intern"),
    location: str = Query(None, example="Bengaluru"),
    pages: int = Query(5, example=5, description="Number of pages to scrape")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    # Pass pages to the scraper
    jobs = await loop.run_in_executor(executor, scrape_naukri_jobs, query, location, pages)
    
    saved_count = 0
    if jobs:
        # Use upsert to avoid duplicates based on job_url
        for job in jobs:
            if "job_url" in job and job["job_url"]:
                result = await naukri_collection.update_one(
                    {"job_url": job["job_url"]},
                    {"$set": job},
                    upsert=True
                )
                if result.upserted_id or result.modified_count > 0:
                    saved_count += 1
            else:
                # If no URL, just insert (less ideal but safe)
                await naukri_collection.insert_one(job)
                saved_count += 1

        # Convert ObjectId to string for JSON serialization
        for job in jobs:
            if "_id" in job:
                job["_id"] = str(job["_id"])

    return {
        "query": query,
        "location": location,
        "total_jobs_scraped": len(jobs),
        "new_or_updated_jobs": saved_count,
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

@app.get("/scrape/gfg")
async def scrape_gfg(
    query: Optional[str] = Query(None, example="anagram"),
    pages: int = Query(1, example=1, description="Number of pages to scrape"),
    company: Optional[str] = Query(None, example="Infosys")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(executor, scrape_gfg_questions, query, pages, company)
    
    if questions:
        # Save to database in the main process
        for q in questions:
            await gfg_collection.update_one(
                {"url": q["url"]},
                {"$set": q},
                upsert=True
            )
            if "_id" in q:
                q["_id"] = str(q["_id"])

    return {
        "query": query,
        "company": company,
        "pages": pages,
        "total_questions_scraped": len(questions),
        "status": "success",
        "data": questions
    }

@app.get("/scrape/exercism")
async def scrape_exercism(
    language: str = Query(..., example="python"),
    pages: int = Query(1, example=1, description="Number of pages to scrape")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    exercises = await loop.run_in_executor(executor, scrape_exercism_questions, language, pages)
    
    if exercises:
        # Save to database in the main process
        for ex in exercises:
            await exercism_collection.update_one(
                {"url": ex["url"]},
                {"$set": ex},
                upsert=True
            )
            if "_id" in ex:
                ex["_id"] = str(ex["_id"])

    return {
        "language": language,
        "pages": pages,
        "total_exercises_scraped": len(exercises),
        "status": "success",
        "data": exercises
    }

@app.get("/scrape/hackerrank")
async def scrape_hackerrank(
    track: str = Query("python", description="Track slug (e.g., python, algorithms)"),
    subdomains: List[str] = Query(..., description="Filter by subdomains (e.g., py-introduction)"),
    status: Optional[List[str]] = Query(None, description="Filter by status (e.g., solved, unsolved)"),
    difficulty: Optional[List[str]] = Query(None, description="Filter by difficulty (e.g., easy, medium)"),
    skills: Optional[List[str]] = Query(None, description="Filter by skills"),
    pages: int = Query(1, ge=1)
):
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(
        executor, 
        scrape_hackerrank_questions, 
        track, subdomains, status, difficulty, skills, pages
    )
    
    if questions:
        for q in questions:
            await hackerrank_collection.update_one(
                {"slug": q["slug"]},
                {"$set": q},
                upsert=True
            )
            if "_id" in q:
                q["_id"] = str(q["_id"])
                
    return {
        "track": track,
        "filters": {
            "status": status,
            "difficulty": difficulty,
            "subdomains": subdomains,
            "skills": skills
        },
        "count": len(questions),
        "data": questions
    }



@app.get("/scrape/codechef")
async def scrape_codechef(
    tag: str = Query(..., example="permutation-cycles"),
    pages: int = Query(1, example=1)
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(executor, scrape_codechef_questions, tag, pages)
    
    if questions:
        for q in questions:
            await codechef_collection.update_one(
                {"url": q["url"]},
                {"$set": q},
                upsert=True
            )
            if "_id" in q:
                q["_id"] = str(q["_id"])
                
    return {
        "tag": tag,
        "pages": pages,
        "total_questions_scraped": len(questions),
        "status": "success",
        "data": questions
    }



@app.get("/scrape/prepinsta")
async def scrape_prepinsta(
    company: str = Query("capgemini", example="capgemini")
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(executor, scrape_prepinsta_questions, company)
    
    if questions:
        for q in questions:
            # Upsert based on title since URL is same for page
            await prepinsta_collection.update_one(
                {"title": q["title"], "company": q["company"]},
                {"$set": q},
                upsert=True
            )
            if "_id" in q:
                q["_id"] = str(q["_id"])
                
    return {
        "company": company,
        "total_questions_scraped": len(questions),
        "status": "success",
        "data": questions
    }


@app.get("/scrape/interviewbit")
async def scrape_interviewbit(
    query: str = Query(..., example="amazon"),
    limit: int = Query(20, example=20)
    ):
    # Run the synchronous blocking scraper in a process pool
    loop = asyncio.get_event_loop()
    questions = await loop.run_in_executor(executor, scrape_interviewbit_questions, query, limit)
    
    if questions:
        for q in questions:
            await interviewbit_collection.update_one(
                {"url": q["url"]},
                {"$set": q},
                upsert=True
            )
            if "_id" in q:
                q["_id"] = str(q["_id"])
                
    return {
        "platform": "InterviewBit",
        "company": query,
        "total_questions_scraped": len(questions),
        "status": "success",
        "data": questions
    }

