from playwright.sync_api import sync_playwright
import time
import random
from urllib.parse import quote_plus

class ZipRecruiterScraper:
    def __init__(self, headless=False):
        """
        Initialize ZipRecruiter scraper (India version)
        """
        self.jobs_data = []
        self.headless = headless
        self.base_url = "https://www.ziprecruiter.in/jobs/search"

    def search_jobs(self, keywords, location, max_pages=1):
        """
        Search for jobs on ZipRecruiter India
        """
        print(f"\n{'='*70}")
        print(f"🔍 ZIPRECRUITER INDIA JOB SCRAPER")
        print(f"{'='*70}")
        print(f"Search: {keywords}")
        print(f"Location: {location}")
        print(f"{'='*70}\n")

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            context = browser.new_context(
                 viewport={'width': 1280, 'height': 800},
                 user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = context.new_page()

            try:
                # Construct search URL
                # Pattern: https://www.ziprecruiter.in/jobs/search?q=...&l=...
                q = quote_plus(keywords)
                l = quote_plus(location) if location else ""
                
                # Base search URL
                url = f"{self.base_url}?q={q}&l={l}"
                
                print(f"🌐 Base URL: {url}")

                for page_num in range(1, max_pages + 1):
                    # Add pagination if needed
                    current_url = url
                    if page_num > 1:
                        current_url = f"{url}&page={page_num}"
                    
                    print(f"\n📄 Scraping page {page_num}...")
                    print(f"   Link: {current_url}")
                    
                    try:
                        page.goto(current_url, timeout=60000, wait_until="domcontentloaded")
                        # Wait for job listings container
                        page.wait_for_selector("ul.jobList, li.job-listing", timeout=10000)
                    except Exception as e:
                        print(f"   ⚠️  Error loading page {page_num}: {e}")
                        break

                    # Slight delay for dynamic content
                    time.sleep(2)

                    # Extract jobs
                    new_jobs = self._extract_jobs(page)
                    
                    if new_jobs == 0:
                        print("   ⚠️  No jobs found on this page. Stopping.")
                        break
                    
                    # Check for next page button to decide if we continue
                    # Selector for next page: ul.pagination li a[rel='next'] or similar
                    has_next = page.query_selector("ul.pagination a[rel='next']") or \
                               page.query_selector("li.active + li a")
                               
                    if not has_next and page_num < max_pages:
                        print("   ℹ️  No next page link found. Finishing.")
                        break
                        
                    time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                print(f"❌ Error during scraping: {e}")
            finally:
                browser.close()

    def _extract_jobs(self, page):
        """Extract jobs from the current HTML page"""
        jobs_found_count = 0
        
        # Select all job list items
        # Based on source: <li class="job-listing ...">
        job_cards = page.query_selector_all("li.job-listing")
        
        print(f"   Found {len(job_cards)} job cards.")

        for card in job_cards:
            try:
                job = {}
                
                # 1. Title and URL
                # Selector: .jobList-title (which is an anchor tag)
                title_elem = card.query_selector(".jobList-title")
                if title_elem:
                    job['title'] = title_elem.inner_text().strip()
                    href = title_elem.get_attribute("href")
                    if href:
                        if href.startswith("http"):
                            job['url'] = href
                        else:
                            job['url'] = "https://www.ziprecruiter.in" + href
                    else:
                        job['url'] = "N/A"
                else:
                    job['title'] = "N/A"
                    job['url'] = "N/A"

                # 2. Company & Location
                # Selector: .jobList-introMeta
                # It usually has <li><i>icon</i> Text</li>
                meta_elem = card.query_selector(".jobList-introMeta")
                job['company'] = "N/A"
                job['location'] = "N/A"
                
                if meta_elem:
                    lis = meta_elem.query_selector_all("li")
                    # Heuristic: Company often has fa-building, Location has fa-map-marker-alt
                    for li in lis:
                        text = li.inner_text().strip()
                        if not text: continue
                        
                        icon_building = li.query_selector(".fa-building")
                        icon_map = li.query_selector(".fa-map-marker-alt")
                        
                        if icon_building:
                            job['company'] = text
                        elif icon_map:
                            job['location'] = text
                        # Fallback by position if icons missing
                        elif job['company'] == "N/A": 
                             job['company'] = text # Assume first text is company
                        elif job['location'] == "N/A" and text != job['company']:
                             job['location'] = text

                # 3. Description Snippet
                # Selector: .jobList-description
                desc_elem = card.query_selector(".jobList-description")
                job['description'] = desc_elem.inner_text().strip() if desc_elem else "N/A"

                # 4. Date
                # Selector: .jobList-date
                date_elem = card.query_selector(".jobList-date")
                job['posted_date'] = date_elem.inner_text().strip() if date_elem else "N/A"

                # Standard fields
                job['salary'] = "N/A" # Not visible in snippet usually
                job['job_type'] = "N/A"
                job['qualifications'] = [] # Detailed extraction needed

                # Add to list
                if job['title'] != "N/A":
                    # Deduplicate
                    if not any(j['url'] == job['url'] for j in self.jobs_data):
                        self.jobs_data.append(job)
                        jobs_found_count += 1
                        print(f"      + {job['title']} at {job['company']}")

            except Exception as e:
                print(f"      Error parsing card: {e}")
                continue
                
        return jobs_found_count

def scrape_ziprecruiter_jobs(query, location="India", max_pages=1):
    scraper = ZipRecruiterScraper(headless=False) # Keep False for safety/debugging as per user preference
    try:
        scraper.search_jobs(query, location, max_pages)
        # Standardize for API response
        results = []
        for j in scraper.jobs_data:
            results.append({
                "keyword": query,
                "title": j.get('title'),
                "company": j.get('company'),
                "location": j.get('location'),
                "salary": j.get('salary'),
                "job_type": j.get('job_type'),
                "qualifications": j.get('qualifications'),
                "job_description": j.get('description'),
                "job_url": j.get('url'),
                "source": "ZipRecruiter"
            })
        return results
    except Exception as e:
        print(f"Global Scrape Error: {e}")
        return []

if __name__ == "__main__":
    q = input("Job Role: ") or "Python Developer"
    l = input("Location: ") or "India"
    jobs = scrape_ziprecruiter_jobs(q, l)
    print(f"Scraped {len(jobs)} jobs.")