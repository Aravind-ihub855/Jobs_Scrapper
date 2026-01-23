from playwright.sync_api import sync_playwright
import time
import random
import os
from datetime import datetime

class GlassdoorScraper:
    def __init__(self, headless=False):
        self.headless = headless
        self.jobs_data = []

    def check_for_verification(self, page):
        """Detect if Cloudflare, bot detection, or 'Zzzzz' error is blocking us"""
        time.sleep(1) # Short settle time
        
        # 0. Check for "Zzzzz" Error Page
        try:
            if page.wait_for_selector('h3:has-text("Zzzzzzzz")', timeout=1000):
                print("      ⚠️ Detected 'Zzzzz' crash page. Reloading...")
                page.reload()
                time.sleep(5)
                return True
        except:
            pass

        page_title = page.title()
        page_content = page.content()
        
        # 1. Check for Cloudflare/Bot detection
        if "Just a moment" in page_title or "Verifying" in page_title or "verify you are human" in page_content.lower():
             print("\n🛑 BOT DETECTION / CAPTCHA DETECTED! (Glassdoor)")
             print("Please solve the verification in the browser window.")
             print("Waiting for you to finish...")
             
             while "Just a moment" in page.title() or "Verifying" in page.title() or "verify you are human" in page.content().lower():
                 time.sleep(2)
             
             print("✅ Verification solved! Proceeding...")
             time.sleep(2)
             page.wait_for_load_state("networkidle")
             return True
        
        # 2. Check for lead capture/signup popups
        try:
            # Escape key to close most popups
            page.keyboard.press("Escape")
            
            # Targeted close buttons for Glassdoor modals
            close_selectors = [
                'button.CloseButton', 
                '.closeButtonWrapper button',
                '[data-test="consolidatedAuth"] button[class*="Close"]',
                'button[aria-label="Close"]', 
                'button[class*="close"]', 
                '.modal-close', 
                '[data-test="modal-close"]'
            ]
            for sel in close_selectors:
                try:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        print(f"      🧹 Dismissing Glassdoor popup via: {sel}")
                        btn.click()
                        time.sleep(1.5)
                except:
                    continue
        except:
            pass
        return False

    def search_jobs(self, keywords, location, max_pages=1):
        print(f"\n======================================================================")
        print(f"🔍 GLASSDOOR JOB SCRAPER")
        print(f"Search: {keywords}")
        print(f"Location: {location}")
        print(f"Max Batches: {max_pages}")
        print(f"======================================================================")

        with sync_playwright() as p:
            print("🚀 Launching browser...")
            browser = p.chromium.launch(
                headless=self.headless,
                args=['--disable-blink-features=AutomationControlled']
            )
            
            context = browser.new_context(
                viewport={'width': 1366, 'height': 768},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36'
            )
            
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = context.new_page()
            self.jobs_data = []

            try:
                # 1. Navigate directly to search
                encoded_keyword = keywords.replace(" ", "+")
                encoded_loc = location.replace(" ", "+")
                
                # Updated URL structure: using .co.in and locId=0
                url = f"https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={encoded_keyword}&locT=C&locId=0&locKeyword={encoded_loc}"
                print(f"🌐 Navigating to: {url}")
                page.goto(url, timeout=60000)
                
                # Human-like pause for page to settle
                time.sleep(random.uniform(3, 5))
                
                # Check for verification immediately
                self.check_for_verification(page)

                # 3. Scrape Loop (Batches)
                for current_batch in range(1, max_pages + 1):
                    # Check for crash page at start of each batch
                    self.check_for_verification(page) 
                    
                    print(f"\n📄 Processing Batch {current_batch}...")
                    
                    # Scroll to top to ensure all items are rendered (if virtualized)
                    if current_batch > 1:
                         # Ensure we aren't crashed before scrolling
                         self.check_for_verification(page) 
                         
                         print("      ⬆️ Scrolling to top to ensure visibility...")
                         page.keyboard.press("Home")
                         time.sleep(2)

                    # A. Scrape currently visible jobs
                    new_jobs = self._extract_jobs_from_page(page)
                    print(f"✅ Batch {current_batch}: Found {new_jobs} unique jobs. (Total: {len(self.jobs_data)})")
                    
                    # DEBUG: Screenshot if 0 jobs found unexpectedly
                    if new_jobs == 0 and current_batch > 1:
                        print("      ⚠️ Found 0 jobs in batch 2+. Saving debug screenshot...")
                        page.screenshot(path="glassdoor_debug.png", full_page=True)

                    # B. Load More (if not last batch)
                    if current_batch < max_pages:
                        print(f"⏭️ Loading more jobs...")
                        
                        # Get count before
                        initial_count = len(page.query_selector_all('li[data-test="jobListing"], li[class*="JobCard"]'))
                        
                        # 1. Scroll-trigger maneuver (Slower = More Human)
                        page.keyboard.press("End")
                        time.sleep(1.5)
                        
                        # Check for verification immediately
                        self.check_for_verification(page)
                        
                        # 2. Click "Show More"
                        show_more_clicked = False
                        more_btn_selectors = [
                            'button[data-test="load-more"]',
                            '[data-test="load-more"]',
                            'button:has-text("Show more jobs")',
                            '[class*="loadMore"]',
                            'button[class*="Button_button"]'
                        ]
                        
                        for sel in more_btn_selectors:
                            try:
                                btn = page.query_selector(sel)
                                if btn and btn.is_visible():
                                    # Scroll into view gently
                                    btn.scroll_into_view_if_needed()
                                    time.sleep(random.uniform(0.5, 1))
                                    
                                    print(f"      🖱️ Clicking '{sel}'")
                                    # Force click sometimes helps with overlays
                                    btn.click(force=True)
                                    show_more_clicked = True
                                    break
                            except:
                                continue
                        
                        if not show_more_clicked:
                            print("🏁 No 'Show More' button found. Stopping.")
                            break

                        # 3. Wait for list growth
                        print("      ⏳ Waiting for new jobs...")
                        try:
                            # Wait up to 15 loops for the list count to increase
                            for i in range(15):
                                current_count = len(page.query_selector_all('li[data-test="jobListing"], li[class*="JobCard"]'))
                                if current_count > initial_count:
                                    print(f"      📈 New jobs loaded! ({initial_count} -> {current_count})")
                                    break
                                
                                # Check for modal in case it blocked the load
                                if i % 2 == 0:
                                    self.check_for_verification(page)
                                    if btn and btn.is_visible():
                                       # Retry click if it's still there
                                       btn.click(force=True)
                                time.sleep(1)
                        except:
                            pass
                        
                        time.sleep(2)

            except Exception as e:
                print(f"❌ Error during scraping: {e}")
            finally:
                context.close()
                browser.close()

        return self.jobs_data



    def _extract_jobs_from_page(self, page):
        # Expanded selectors for different Glassdoor layouts
        card_selectors = [
            '[data-test="jobListing"]',
            'li[class*="JobCard"]',
            'article[class*="JobCard"]',
            'div[class*="JobCard"]',
            'li[class*="JobListing"]',
            'ul[class*="job-search-key"] > li',
            'ol > li'
        ]
        
        job_elements = []
        for sel in card_selectors:
            try:
                elements = page.query_selector_all(sel)
                # Removed strict > 2 check. If we find even 1, take it.
                if elements:
                    job_elements = elements
                    print(f"      [DEBUG] Found {len(job_elements)} cards via: {sel}")
                    break
            except:
                continue

        print(f"🔍 Found {len(job_elements)} job elements on current page.")
        new_count = 0
        
        for idx, element in enumerate(job_elements, 1):
            try:
                # 0. Quick filter: skip if element is hidden or very small
                # REMOVED is_visible check because virtualized elements might be "hidden" from viewport
                # but still present in DOM.
                
                # Get ID for duplicate checking
                brand_views = element.get_attribute('data-brandviews') or ""
                jlid = ""
                if "jlid=" in brand_views:
                    jlid = brand_views.split("jlid=")[1].split(":")[0].split("|")[0].strip()
                
                if jlid and any(f"jl={jlid}" in j['url'] for j in self.jobs_data):
                    continue

                # CLICK to load description
                # Only click if we haven't seen it, and handle scroll
                print(f"      👉 Selecting job {idx}...")
                try:
                    element.scroll_into_view_if_needed()
                    element.click(force=True)
                except:
                    # If we can't click it, try to just parse it anyway
                    pass
                
                time.sleep(1) 
                
                job = self._parse_job_details(element, page)
                
                if job and job.get('title') and job['title'] != 'N/A':
                    # Prevent duplicates by title/company
                    if not any(j['title'] == job['title'] and j['company'] == job['company'] for j in self.jobs_data):
                        self.jobs_data.append(job)
                        new_count += 1
                        print(f"      ✓ Scraped: {job['title']} at {job['company']}")
            except Exception as e:
                print(f"      ⚠️ Skip job {idx}: {e}")
        return new_count

    def _parse_job_details(self, card_element, page):
        job = {
            'title': 'N/A',
            'company': 'N/A',
            'location': 'N/A',
            'salary': 'N/A',
            'description': 'N/A',
            'url': 'N/A',
            'job_type': 'N/A',
            'posted_date': str(datetime.now().date()),
            'source': 'Glassdoor'
        }

        try:
            # 1. Title
            title_elem = card_element.query_selector('[data-test="job-title"]') or card_element.query_selector('a[class*="jobTitle"]')
            if title_elem:
                job['title'] = title_elem.inner_text().strip()

            # 2. Company
            comp_selectors = [
                '[data-test="employer-short-name"]',
                'span[class*="EmployerName"]',
                'span[class*="companyName"]',
                '.EmployerProfile_employerName__'
            ]
            for c_sel in comp_selectors:
                comp_elem = card_element.query_selector(c_sel)
                if comp_elem:
                    job['company'] = comp_elem.inner_text().split('(')[0].split('\n')[0].strip()
                    break

            # 3. Location
            loc_elem = (
                card_element.query_selector('[data-test="location"]') or 
                card_element.query_selector('div[class*="location"]') or
                card_element.query_selector('.JobCard_location__')
            )
            if loc_elem:
                job['location'] = loc_elem.inner_text().strip()

            # 4. Salary
            sal_elem = card_element.query_selector('[data-test="detailSalary"]') or card_element.query_selector('span[data-test="salary-estimate"]')
            if sal_elem:
                job['salary'] = sal_elem.inner_text().strip()

            # 5. Job ID / URL
            # Look for jlid in data-brandviews
            brand_views = card_element.get_attribute('data-brandviews') or ""
            jlid = ""
            if "jlid=" in brand_views:
                try:
                    jlid = brand_views.split("jlid=")[1].split(":")[0].split("|")[0].strip()
                except:
                    pass
            
            if jlid:
                job['url'] = f"https://www.glassdoor.com/job-listing/-.htm?jl={jlid}"
            else:
                # Fallback to direct link in card
                link_elem = card_element.query_selector('a[data-test="job-title"]') or card_element.query_selector('a[class*="jobTitle"]')
                if link_elem:
                    href = link_elem.get_attribute('href')
                    if href:
                        job['url'] = "https://www.glassdoor.com" + href if href.startswith('/') else href

            # 6. Description (from details pane)
            # Based on user-provided HTML class: JobDetails_jobDescription__uW_fK
            desc_selectors = [
                '.JobDetails_jobDescription__uW_fK',
                '[data-test="jobDescription"]',
                '.jobDescriptionContent',
                'div[class*="JobDetails_jobDescription"]',
                '.job-description'
            ]
            for sel in desc_selectors:
                desc_elem = page.query_selector(sel)
                if desc_elem and desc_elem.is_visible():
                    text = desc_elem.inner_text().strip()
                    if len(text) > 50:
                        job['description'] = text[:2000]
                        break

            return job
        except Exception as e:
            print(f"      [DEBUG] Parsing error: {e}")
            return job

def scrape_glassdoor_jobs(query, location="United States", max_pages=1):
    scraper = GlassdoorScraper(headless=False) # Keep False to manually handle Cloudflare if needed
    return scraper.search_jobs(query, location, max_pages)

if __name__ == "__main__":
    from app.database import glassdoor_collection
    import asyncio

    async def test_and_save():
        jobs = scrape_glassdoor_jobs("Software Engineer", "New York, NY", max_pages=1)
        if jobs:
            try:
                # Add source field if missing
                for j in jobs:
                    j['source'] = 'Glassdoor'
                
                # Insert into MongoDB
                # Since this is a sync script but database is async, we use a small bridge
                from motor.motor_asyncio import AsyncIOMotorClient
                import os
                
                # Check directly from env for the standalone test
                client = AsyncIOMotorClient(os.getenv("MONGO_URI"))
                db = client[os.getenv("DB_NAME")]
                col = db["glassdoor_jobs"]
                
                print(f"\n💾 Saving {len(jobs)} jobs to MongoDB...")
                await col.insert_many(jobs)
                print("✅ Successfully saved to 'glassdoor_jobs' collection!")
            except Exception as e:
                print(f"❌ DB Save Error: {e}")
        
        print(f"\n🚀 Samples:")
        for j in jobs[:3]:
            print(f"- {j['title']} at {j['company']} ({j['url']})")

    asyncio.run(test_and_save())
