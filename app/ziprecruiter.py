from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import pandas as pd
import json
import time
import random


class ZipRecruiterScraper:
    def __init__(self, headless=False):
        """
        Initialize ZipRecruiter scraper
        headless=False recommended for avoiding detection
        """
        self.jobs_data = []
        self.headless = headless
        
    def search_jobs(self, keywords, location, max_pages=1):
        """
        Search for jobs on ZipRecruiter
        """
        print(f"\n{'='*70}")
        print(f"🔍 ZIPRECRUITER JOB SCRAPER")
        print(f"{'='*70}")
        print(f"Search: {keywords}")
        print(f"Location: {location}")
        print(f"Max Pages: {max_pages}")
        print(f"{'='*70}\n")
        
        with sync_playwright() as p:
            # Launch browser with stealth settings
            print("🚀 Launching browser...")
            browser = p.chromium.launch(
                headless=self.headless,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            # Create context with realistic settings
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Remove automation indicators
            context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            page = context.new_page()
            
            try:
                # Build search URL
                base_url = "https://www.ziprecruiter.com/jobs-search"
                search_url = f"{base_url}?search={keywords.replace(' ', '+')}&location={location.replace(' ', '+')}"
                
                print(f"🌐 Navigating to: {search_url}\n")
                
                for page_num in range(1, max_pages + 1):
                    print(f"📄 Scraping page {page_num}...")
                    
                    # Add page parameter if not first page
                    current_url = f"{search_url}&page={page_num}" if page_num > 1 else search_url
                    
                    # Navigate with timeout
                    try:
                        page.goto(current_url, wait_until='domcontentloaded', timeout=60000)
                    except PlaywrightTimeout:
                        print(f"   ⚠️  Timeout loading page {page_num}, trying anyway...")
                    
                    # Wait for Cloudflare verification
                    print("   ⏳ Waiting for Cloudflare verification...")
                    time.sleep(5)
                    self.check_for_verification(page)
                    
                    # Wait for actual content to load
                    print("   ⏳ Waiting for job listings to render...")
                    time.sleep(5)
                    
                    # Try to wait for specific job-related content
                    job_loaded = False
                    selectors_to_try = [
                        'h2',  # Job titles are usually in h2
                        'a[href*="/c/"]',  # Company links
                        'article',
                        'li[role="listitem"]',
                        'div[id*="job"]',
                    ]
                    
                    for selector in selectors_to_try:
                        try:
                            # Wait for at least one article or job listing
                            page.wait_for_selector(selector, timeout=15000)
                            elements = page.query_selector_all(selector)
                            if len(elements) > 2:  # Found some jobs
                                print(f"   ✓ Found content with: {selector} ({len(elements)} elements)")
                                job_loaded = True
                                break
                        except PlaywrightTimeout:
                            continue
                    
                    if not job_loaded:
                        print("   ⚠️  Could not confirm job listings loaded")
                    
                    # Additional wait for full rendering
                    time.sleep(3)
                    
                    # Scroll to load lazy content
                    print("   📜 Scrolling page...")
                    self._scroll_page(page)
                    
                    # Extract jobs from current page
                    jobs_found = self._extract_jobs(page, page_num)
                    
                    if jobs_found == 0:
                        print(f"   ⚠️  No jobs found on page {page_num}. Stopping.")
                        break
                    
                    # Check for next page
                    if page_num < max_pages and not self._has_next_page(page):
                        print(f"   ℹ️  No more pages available")
                        break
                    
                    # Human-like delay between pages
                    if page_num < max_pages:
                        delay = random.uniform(3, 6)
                        print(f"   ⏸️  Waiting {delay:.1f}s before next page...")
                        time.sleep(delay)
                
                print(f"\n{'='*70}")
                print(f"✅ Scraping complete!")
                print(f"📊 Total jobs scraped: {len(self.jobs_data)}")
                print(f"{'='*70}\n")
                
            except Exception as e:
                print(f"\n❌ Error during scraping: {e}")
            finally:
                browser.close()

    def check_for_verification(self, page):
        """Detect if Cloudflare or bot detection is blocking us"""
        page_title = page.title()
        page_content = page.content()
        
        if "Just a moment" in page_title or "Verifying" in page_title or "verify you are human" in page_content.lower():
             print("\n🛑 BOT DETECTION / CAPTCHA DETECTED! (ZipRecruiter)")
             print("Please solve the verification in the browser window.")
             print("Waiting for you to finish...")
             
             # Pause until title changes or verification is gone
             while "Just a moment" in page.title() or "Verifying" in page.title() or "verify you are human" in page.content().lower():
                 time.sleep(2)
             
             print("✅ Verification solved! Proceeding...")
             time.sleep(2)
             return True
        return False
    
    def _scroll_page(self, page):
        """Scroll page to trigger lazy loading"""
        try:
            for i in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1)
        except Exception as e:
            print(f"      ⚠️  Scroll warning: {e}")
    
    def _extract_jobs(self, page, page_num):
        """Extract job listings from current page"""
        jobs_found = 0
        
        try:
            # Multiple selector strategies for ZipRecruiter
            selectors = [
                'article',
                'div[data-job-id]',
                'li[role="listitem"]',
                'div[id^="job_"]',
                'li[class*="job"]',
                'div[class*="JobListing"]'
            ]
            
            job_elements = []
            for selector in selectors:
                try:
                    job_elements = page.query_selector_all(selector)
                    if len(job_elements) > 2:
                        print(f"      ✓ Found {len(job_elements)} jobs using selector: {selector}")
                        break
                except:
                    continue
            
            if len(job_elements) == 0:
                return 0
            
            # Parse each job
            for idx, element in enumerate(job_elements[:50], 1):  # Limit to 50 per page
                try:
                    job_data = self._parse_job_element(element)
                    
                    if job_data and job_data.get('title') != 'N/A':
                        if not any(j['title'] == job_data['title'] and j['company'] == job_data['company'] for j in self.jobs_data):
                            self.jobs_data.append(job_data)
                            jobs_found += 1
                            print(f"      ✓ Job {jobs_found}: {job_data['title'][:45]}...")
                            
                except Exception as e:
                    continue
            
            return jobs_found
            
        except Exception as e:
            print(f"      ❌ Error extracting jobs: {e}")
            return 0
    
    def _parse_job_element(self, element):
        """Parse individual job element"""
        job = {
            'title': 'N/A',
            'company': 'N/A',
            'location': 'N/A',
            'salary': 'N/A',
            'description': 'N/A',
            'url': 'N/A',
            'job_type': 'N/A',
            'posted_date': 'N/A'
        }
        
        try:
            # Extract job title
            title_selectors = ['a[aria-label^="View "]', 'h2 a', 'h2', 'h3 a', 'h3']
            for selector in title_selectors:
                try:
                    title_elem = element.query_selector(selector)
                    if title_elem:
                        text = title_elem.inner_text().strip()
                        if text and len(text) > 3:
                            job['title'] = text
                            href = title_elem.get_attribute('href')
                            if href:
                                if href.startswith('/'):
                                    job['url'] = f"https://www.ziprecruiter.com{href}"
                                elif 'ziprecruiter.com' in href:
                                    job['url'] = href
                            break
                except:
                    continue
            
            # Extract company
            company_selectors = ['a[href*="/co/"]', 'a[class*="company"]', 'span[class*="company"]', 'div[class*="company"]']
            for selector in company_selectors:
                try:
                    company_elem = element.query_selector(selector)
                    if company_elem:
                        text = company_elem.inner_text().strip()
                        if text and len(text) > 1:
                            job['company'] = text
                            break
                except:
                    continue
            
            # Extract location
            location_selectors = ['span[class*="location"]', 'div[class*="location"]', 'a[class*="location"]']
            for selector in location_selectors:
                try:
                    location_elem = element.query_selector(selector)
                    if location_elem:
                        text = location_elem.inner_text().strip()
                        if text and len(text) > 2:
                            job['location'] = text
                            break
                except:
                    continue
            
            # Extract salary
            salary_selectors = ['span[class*="salary"]', 'div[class*="salary"]', 'span[class*="compensation"]']
            for selector in salary_selectors:
                try:
                    salary_elem = element.query_selector(selector)
                    if salary_elem:
                        text = salary_elem.inner_text().strip()
                        if text and ('$' in text or 'K' in text):
                            job['salary'] = text
                            break
                except:
                    continue
            
            # Extract description
            desc_selectors = ['p[class*="snippet"]', 'div[class*="snippet"]', 'p', 'span[class*="description"]']
            for selector in desc_selectors:
                try:
                    desc_elem = element.query_selector(selector)
                    if desc_elem:
                        text = desc_elem.inner_text().strip()
                        if len(text) > 20:
                            job['description'] = text[:300]
                            break
                except:
                    continue
            
            return job
        except:
            return job
    
    def _has_next_page(self, page):
        """Check if there's a next page"""
        try:
            next_selectors = ['a[aria-label*="Next"]', 'button[aria-label*="Next"]', 'a.next-page']
            for selector in next_selectors:
                next_btn = page.query_selector(selector)
                if next_btn and next_btn.is_visible():
                    return True
            return False
        except:
            return False


def scrape_ziprecruiter_jobs(query, location="India"):
    scraper = ZipRecruiterScraper(headless=True)
    try:
        scraper.search_jobs(keywords=query, location=location, max_pages=1)
        
        # Standardize data format
        standardized_jobs = []
        for job in scraper.jobs_data:
            standardized_job = {
                "keyword": query,
                "title": job.get('title', 'N/A'),
                "company": job.get('company', 'N/A'),
                "location": job.get('location', 'N/A'),
                "salary": job.get('salary', 'N/A'),
                "job_type": job.get('job_type', 'N/A'),
                "qualifications": [],
                "job_description": job.get('description', 'N/A'),
                "job_url": job.get('url', 'N/A'),
                "source": "ZipRecruiter"
            }
            standardized_jobs.append(standardized_job)
        
        return standardized_jobs
    finally:
        # No explicit close needed logic here if we use context manager in search_jobs, 
        # but the class doesn't use it. We'll rely on the class closing logic.
        pass


# Main execution
if __name__ == "__main__":
    print("\n" + "="*70)
    print("ZIPRECRUITER JOB SCRAPER")
    print("="*70 + "\n")
    
    JOB_QUERY = input("Enter Job Role (e.g. Python Developer): ")
    JOB_LOCATION = input("Enter Location (e.g. India or Remote): ")
    
    if not JOB_QUERY:
        JOB_QUERY = "Full Stack Developer"
    if not JOB_LOCATION:
        JOB_LOCATION = "India"
        
    jobs = scrape_ziprecruiter_jobs(JOB_QUERY, JOB_LOCATION)
    
    if jobs:
        print(f"\n✅ Scraped {len(jobs)} jobs successfully!")
        for j in jobs[:3]:
            print(f"- {j['title']} at {j['company']}")
    else:
        print("\n❌ No jobs found.")