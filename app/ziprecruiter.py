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
        print(f"ZIPRECRUITER INDIA JOB SCRAPER")
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
                
                print(f"Base URL: {url}")

                # Use the provided max_pages parameter
                for page_num in range(1, max_pages + 1):
                    # Add pagination if needed
                    current_url = url
                    if page_num > 1:
                        current_url = f"{url}&page={page_num}"
                    
                    print(f"\nScraping page {page_num}...")
                    print(f"   Link: {current_url}")
                    
                    try:
                        page.goto(current_url, timeout=60000, wait_until="domcontentloaded")
                        # Wait for job listings container
                        page.wait_for_selector("ul.jobList, li.job-listing, .jobList-title", timeout=15000)
                    except Exception as e:
                        print(f"     Error loading page {page_num}: {e}")
                        break

                    # Slight delay for dynamic content
                    time.sleep(2)

                    # Extract job URLs from the search page
                    job_links = self._get_job_links(page)
                    
                    if not job_links:
                        print("    No job links found on this search page.")
                        break
                    
                    print(f"   Found {len(job_links)} jobs to scrape details for.")
                    
                    # Visit each job URL to get full details
                    for idx, link in enumerate(job_links, 1):
                        try:
                            # Visit detail page
                            detail_page = context.new_page()
                            detail_page.goto(link, timeout=45000, wait_until="domcontentloaded")
                            time.sleep(random.uniform(1, 2))
                            
                            job_data = self._scrape_job_details(detail_page, link)
                            if job_data:
                                self.jobs_data.append(job_data)
                                print(f"      [{idx}/{len(job_links)}] Scraped: {job_data['title'][:40]}...")
                            
                            detail_page.close()
                        except Exception as e:
                            print(f"      Failed to scrape job {link}: {e}")
                            try: detail_page.close() 
                            except: pass

                    # Smart stop: check for next button
                    if page_num < max_pages:
                        has_next = page.query_selector("ul.pagination a[rel='next']") or \
                                   page.query_selector("li.active + li a") or \
                                   page.query_selector("a:has-text('Next')")
                                   
                        if not has_next:
                            print("   No next page link found. Finishing loop.")
                            break
                        
                    time.sleep(random.uniform(1, 2))
            
            except Exception as e:
                print(f"Error during scraping: {e}")
            finally:
                browser.close()

    def _get_job_links(self, page):
        """Extract all job URLs from the search results page"""
        links = []
        try:
            # Selector derived from search page: .jobList-title (anchor)
            elements = page.query_selector_all(".jobList-title")
            for el in elements:
                href = el.get_attribute("href")
                if href:
                    if href.startswith("http"):
                        links.append(href)
                    else:
                        links.append("https://www.ziprecruiter.in" + href)
        except Exception as e:
            print(f"   Error extracting links: {e}")
        return links

    def _scrape_job_details(self, page, url):
        """Extract full details from the job detail page"""
        job = {
            "title": "N/A",
            "company": "N/A",
            "location": "N/A",
            "description": "N/A",
            "posted_date": "N/A",
            "job_type": "N/A",
            "salary": "N/A",
            "url": url
        }
        
        try:
            # 1. Title
            # <h1 class="u-mv--remove u-textH2">
            title_el = page.query_selector("h1.u-textH2") or page.query_selector("h1")
            if title_el:
                job['title'] = title_el.inner_text().strip()

            # 2. Company
            # <div class="text-primary text-large"><strong>Paresha HR Service PVT LTD</strong></div>
            company_el = page.query_selector(".text-primary.text-large strong")
            if company_el:
                job['company'] = company_el.inner_text().strip()
            
            # 3. Location
            # <span><i class="fas fa-map-marker-alt"></i><span class="u-ml--xsmall">Coimbatore, Tamil Nadu, IN</span></span>
            # We look for the container with map marker
            loc_el = page.query_selector(":has(.fa-map-marker-alt) > .u-ml--xsmall")
            if loc_el:
                job['location'] = loc_el.inner_text().strip()

            # 4. Job Type (Full Time etc)
            # <i class="fas fa-hourglass" ...></i><span class="u-ml--xsmall">Full Time</span>
            type_el = page.query_selector(":has(.fa-hourglass) > .u-ml--xsmall")
            if type_el:
                job['job_type'] = type_el.inner_text().strip()
                
            # 5. Posted Date
            # <div class="text-muted"><span>Posted 16 January, 2026</span></div>
            date_el = page.query_selector("div.text-muted span")
            if date_el and "Posted" in date_el.inner_text():
                job['posted_date'] = date_el.inner_text().replace("Posted", "").strip()

            # 6. Description
            # <div class="job-body">...</div>
            desc_el = page.query_selector(".job-body")
            if desc_el:
                # Get the full text, preserving some structure with newlines if possible
                job['description'] = desc_el.inner_text().strip()
            
            # 7. Apply URL (if external)
            apply_btn = page.query_selector("a.external_apply")
            if apply_btn:
                ext_url = apply_btn.get_attribute("href")
                if ext_url:
                     # For API consistency, keep the ZR url as main, but maybe note this?
                     # We'll just keep the detailed page URL as the job URL for now as it's stable.
                     pass

            return job
            
        except Exception as e:
            print(f"        Partial error scraping details: {e}")
            return job

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
                "posted_date": j.get('posted_date'),
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