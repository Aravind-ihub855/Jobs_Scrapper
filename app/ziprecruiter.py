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
            # Force a mobile viewport to trigger the layout with job snippets
            context = browser.new_context(
                viewport={'width': 500, 'height': 1000},
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 14_8 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1'
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
                encoded_keywords = keywords.replace(' ', '+')
                encoded_location = location.replace(' ', '+')
                search_url = f"{base_url}?search={encoded_keywords}&location={encoded_location}"
                
                # If location is Remote, ZipRecruiter often prefers this parameter for better results
                if 'remote' in location.lower():
                    search_url += "&refine_by_location_type=remote"
                
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
                        'article',
                        '[id^="job-card-"]',
                        '.job_result_two_pane_v2',
                        'h2[aria-label]',
                        'div[data-job-id]',
                    ]
                    
                    for selector in selectors_to_try:
                        try:
                            # Wait for at least one article or job listing
                            print(f"   ⏳ Waiting for elements matching: {selector}")
                            page.wait_for_selector(selector, timeout=10000)
                            elements = page.query_selector_all(selector)
                            if len(elements) >= 2:  # Found some jobs
                                print(f"   ✓ Found content with: {selector} ({len(elements)} elements)")
                                job_loaded = True
                                break
                        except:
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
        
        # 1. Check for Cloudflare/Bot detection
        if "Just a moment" in page_title or "Verifying" in page_title or "verify you are human" in page_content.lower():
             print("\n🛑 BOT DETECTION / CAPTCHA DETECTED! (ZipRecruiter)")
             print("Please solve the verification in the browser window.")
             print("Waiting for you to finish...")
             
             while "Just a moment" in page.title() or "Verifying" in page.title() or "verify you are human" in page.content().lower():
                 time.sleep(2)
             
             print("✅ Verification solved! Proceeding...")
             time.sleep(2)
             return True
        
        # 2. Check for Email/Lead Capture Popups (The "732 open positions" modal)
        self._handle_popups(page)
        return False
    
    def _handle_popups(self, page):
        """Dismiss marketing popups and email modals"""
        try:
            # Common close button selectors for ZipRecruiter modsls
            close_selectors = [
                'button[aria-label="Close"]',
                'button[class*="close"]',
                '.modal-close',
                '[data-testid="modal-close"]',
                '#close_modal'
            ]
            
            # 1. Try hitting Escape key first (works on most modshs)
            page.keyboard.press("Escape")
            
            # 2. Try clicking close buttons
            for selector in close_selectors:
                close_btn = page.query_selector(selector)
                if close_btn and close_btn.is_visible():
                    print(f"      🧹 Dismissing popup modal via: {selector}")
                    close_btn.click()
                    time.sleep(1)
        except:
            pass
    
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
                '[id^="job-card-"]',
                '.job_result_two_pane_v2',
                'div[data-job-id]',
                'li[role="listitem"]',
                'div[id^="job_"]'
            ]
            
            job_elements = []
            for selector in selectors:
                try:
                    job_elements = page.query_selector_all(selector)
                    if len(job_elements) >= 2:
                        print(f"      ✓ Found {len(job_elements)} potential job elements using: {selector}")
                        break
                except:
                    continue
            
            if len(job_elements) == 0:
                # Last resort: try any button with an aria-label that looks like a job title
                job_elements = page.query_selector_all('button[aria-label^="View "]')
                if job_elements:
                    print(f"      ✓ Using fallback button-based extraction ({len(job_elements)} found)")
            
            if len(job_elements) == 0:
                return 0
            
            # Parse each job
            for idx, element in enumerate(job_elements[:50], 1):  # Limit to 50 per page
                try:
                    # Periodically check for popups that might appear during scraping
                    if idx % 5 == 0:
                        self._handle_popups(page)

                    # CLICK the job using JS to ensure it triggers even if partially blocked
                    print(f"      👉 Selecting job {idx} to load details...")
                    try:
                        # Use JS click as it's more robust against overlays
                        page.evaluate("el => el.click()", element)
                        time.sleep(1.5) # Wait for details to load
                    except:
                        pass
                        
                    job_data = self._parse_job_element(element, page) # Pass page to parse from any pane
                    
                    if job_data and job_data.get('title') != 'N/A':
                        if not any(j['title'] == job_data['title'] and j['company'] == job_data['company'] for j in self.jobs_data):
                            self.jobs_data.append(job_data)
                            jobs_found += 1
                            print(f"      ✓ Job {jobs_found}: {job_data['title'][:45]}...")
                            
                except Exception as e:
                    print(f"      [DEBUG] Error processing job {idx}: {e}")
                    continue
            
            return jobs_found
            
        except Exception as e:
            print(f"      ❌ Error extracting jobs: {e}")
            return 0
    
    def _parse_job_element(self, element, page=None):
        """Parse individual job element and optionally pull description from the page details pane"""
        job = {
            'title': 'N/A',
            'company': 'N/A',
            'location': 'N/A',
            'salary': 'N/A',
            'description': 'N/A',
            'url': 'N/A',
            'job_type': 'N/A',
            'posted_date': 'N/A',
            'qualifications': []
        }
        
        try:
            # --- DIAGNOSTIC LOGGING ---
            all_text = element.inner_text().replace('\n', ' | ')
            print(f"\n      [DEBUG] Card Raw Text: {all_text[:150]}...")
            # --------------------------

            # 1. Job ID and URL
            try:
                article_id = element.get_attribute('id')
                article_data_id = element.get_attribute('data-job-id')
                
                job_id = None
                if article_id and 'job-card-' in article_id:
                    job_id = article_id.replace('job-card-', '')
                elif article_data_id:
                    job_id = article_data_id
                
                if job_id:
                    # The "Direct Job Link" format with /i/ prefix to avoid 404s
                    job['url'] = f"https://www.ziprecruiter.com/jobs/i/{job_id}"
                    print(f"      [DEBUG] Constructed Direct URL: {job['url']}")
                else:
                    # Fallback to finding any link
                    link_elem = element.query_selector('a[href*="/jobs/"], a[href*="/job/"]')
                    if link_elem:
                        job['url'] = link_elem.get_attribute('href')
                        print("      [DEBUG] URL found via fallback link")
            except Exception as e:
                print(f"      [DEBUG] URL Error: {e}")

            # 2. Extract Title
            title_selectors = [
                'h2[aria-label]',
                'h2',
                'button[aria-label^="View "]',
                '[data-testid="job-card-title"]'
            ]
            
            for sel in title_selectors:
                title_elem = element.query_selector(sel)
                if title_elem:
                    text = title_elem.inner_text().strip()
                    if not text:
                        aria = title_elem.get_attribute('aria-label')
                        if aria:
                            text = aria.replace('View ', '').strip()
                    
                    if text:
                        job['title'] = text
                        print(f"      [DEBUG] Title found via: {sel}")
                        break
            
            # 3. Extract Company
            company_elem = element.query_selector('[data-testid="job-card-company"]')
            if company_elem:
                job['company'] = company_elem.inner_text().strip()
            
            # 4. Extract Location and Job Type (They are siblings)
            location_elem = element.query_selector('[data-testid="job-card-location"]')
            if location_elem:
                job['location'] = location_elem.inner_text().strip()
                
                # Job Type is often the text next to location: "Location · Remote"
                try:
                    parent_p = location_elem.evaluate_handle("el => el.parentElement")
                    full_text = parent_p.as_element().inner_text()
                    if '·' in full_text:
                        job['job_type'] = full_text.split('·')[-1].strip()
                except:
                    pass

            # 5. Extract Salary
            salary_elem = element.query_selector('div.break-all p')
            if salary_elem:
                job['salary'] = salary_elem.inner_text().strip()
            
            # 6. Fallback for Salary (if not in break-all)
            if job['salary'] == 'N/A':
                salary_text_elem = element.query_selector('p:has-text("$")')
                if salary_text_elem:
                    job['salary'] = salary_text_elem.inner_text().strip()

            # 7. Description Snippet (CLICK & CAPTURE strategy)
            # First try the card itself (rarely works now)
            desc_selectors = ['div[class*="snippet"]', 'p.text-body-md:not(:has-text("$"))']
            for d_sel in desc_selectors:
                desc_elem = element.query_selector(d_sel)
                if desc_elem:
                    text = desc_elem.inner_text().strip()
                    if '$' not in text and '·' not in text and len(text) > 10:
                        job['description'] = text[:300]
                        break
            
            # If still N/A, pull from the FULL PAGE details pane (loaded after click)
            if job['description'] == 'N/A' and page:
                try:
                    # Extended detail selectors for current ZipRecruiter layout
                    detail_selectors = [
                        '.job_description', 
                        '.job_details', 
                        '[data-testid="job-description"]', 
                        '#job-details',
                        '.job_description_container',
                        'div[class*="jobDescription"]'
                    ]
                    for det_sel in detail_selectors:
                        detail_elem = page.query_selector(det_sel)
                        if detail_elem and detail_elem.is_visible():
                            full_text = detail_elem.inner_text().strip()
                            if len(full_text) > 50:
                                job['description'] = full_text[:1200]
                                print(f"      [DEBUG] Description captured from DETAILS PANE ({len(full_text)} chars)")
                                break
                except:
                    pass
            
            if job['description'] == 'N/A':
                print("      [DEBUG] Description NOT found even in details pane")

            return job
        except Exception as e:
            print(f"      ❌ Parsing error: {e}")
            return job
        
    def _has_next_page(self, page):
        """Check if there's a next page"""
        try:
            next_selectors = [
                'button[title="Next Page"]',
                'a[aria-label*="Next"]', 
                'button[aria-label*="Next"]', 
                'a.next-page', 
                '[data-testid="pagination-next"]'
            ]
            for selector in next_selectors:
                next_btn = page.query_selector(selector)
                if next_btn and next_btn.is_visible() and not next_btn.is_disabled():
                    return True
            return False
        except:
            return False


def scrape_ziprecruiter_jobs(query, location="India", max_pages=1):
    # Set headless=False so the user can solve captchas if they appear
    scraper = ZipRecruiterScraper(headless=False)
    try:
        scraper.search_jobs(keywords=query, location=location, max_pages=max_pages)
        
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
                "qualifications": job.get('qualifications', []),
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