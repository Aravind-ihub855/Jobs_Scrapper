"""
Monster.com Job Scraper using Playwright (Windows Compatible)

Prerequisites:
pip install playwright pandas playwright-stealth
playwright install chromium

This version uses Playwright with stealth which handles anti-bot detection effectively.
"""

import pandas as pd
import time
import json
import sys
import random
from playwright.sync_api import sync_playwright
try:
    from playwright_stealth import stealth_sync
except ImportError:
    stealth_sync = None


class MonsterScraper:
    def __init__(self, headless=False):
        """
        Initialize the scraper with Playwright and stealth settings
        """
        print("🚀 Initializing Playwright browser...")
        
        try:
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.launch(headless=headless)
            
            # Create context with realistic settings
            self.context = self.browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={'width': 1920, 'height': 1080},
                device_scale_factor=1,
            )
            
            self.page = self.context.new_page()
            
            # Apply stealth if available
            if stealth_sync:
                stealth_sync(self.page)
                print("✓ Applied Playwright Stealth settings")
            
            print("✓ Playwright browser initialized")
            
        except Exception as e:
            print(f"\n❌ ERROR initializing Playwright: {e}")
            if hasattr(self, 'playwright'):
                self.playwright.stop()
            sys.exit(1)
        
        self.jobs_data = []

    def check_for_captcha(self):
        """Detect if DataDome is blocking us"""
        url = self.page.url.lower()
        content = self.page.content()
        
        if "captcha" in url or "geo.captcha-delivery.com" in content:
             print("\n🛑 CAPTCHA DETECTED! (DataDome)")
             print("Please solve the CAPTCHA in the browser window.")
             print("Waiting for you to finish...")
             
             # Pause until URL changes or CAPTCHA is gone
             while "captcha" in self.page.url.lower() or "geo.captcha-delivery.com" in self.page.content():
                 time.sleep(2)
             
             print("✅ CAPTCHA solved! Proceeding...")
             time.sleep(2)
             return True
        return False
    
    def search_jobs(self, keywords, location, max_pages=1):
        """Search for jobs with anti-bot evasion"""
        try:
            # Construct the search URL
            base_url = "https://www.monster.com/jobs/search"
            # Monster uses specific formatting for search queries
            q = keywords.replace(' ', '-')
            where = location.replace(' ', '-')
            url = f"{base_url}?q={q}&where={where}"
            
            print(f"\n🔍 Searching Monster.com: {keywords} in {location}")
            
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(5)
            
            for page_num in range(1, max_pages + 1):
                self.check_for_captcha()
                
                print(f"📄 Processing page {page_num}...")
                
                # Human-like scroll
                print("   📜 Scrolling to load jobs...")
                for _ in range(3):
                    scroll_amount = random.randint(600, 900)
                    self.page.evaluate(f"window.scrollBy(0, {scroll_amount});")
                    time.sleep(random.uniform(1, 2.5))
                
                # Extract
                jobs_found = self._extract_jobs()
                
                if jobs_found == 0:
                    # Check if blocked, otherwise just scroll more
                    if self.check_for_captcha():
                        jobs_found = self._extract_jobs()
                
                print(f"   📊 Found {jobs_found} new jobs on this page")
                
                # Attempt to go to the next page
                if page_num < max_pages:
                    print("   ➡️ Looking for next page...")
                    if self._has_next_page():
                        try:
                            # Try multiple selectors for the next button
                            next_selectors = [
                                "a[aria-label*='Next']", 
                                "button[aria-label*='Next']", 
                                "a[class*='next']", 
                                "[class*='pagination'] a:last-child"
                            ]
                            
                            clicked = False
                            for sel in next_selectors:
                                next_btn = self.page.query_selector(sel)
                                if next_btn and next_btn.is_visible():
                                    next_btn.click()
                                    clicked = True
                                    break
                            
                            if clicked:
                                print("   ✅ Clicked next page button.")
                                time.sleep(random.uniform(3, 5)) # Wait for next page to load
                            else:
                                print("   ⚠️ Next button found but not clickable.")
                                break
                        except Exception as e:
                            print(f"   ⚠️ Could not click next page button: {e}")
                            break # Exit loop if next button not found or clickable
                    else:
                        print("   🔚 No more pages found.")
                        break
                
        except Exception as e:
            print(f"      ⚠️  Search warning: {e}")
    
    def _extract_jobs(self):
        """Extract job information from the current page"""
        jobs_found = 0
        
        try:
            # Wait a bit for jobs to render
            time.sleep(2)
            
            # Multiple selector strategies for Monster.com
            selectors = [
                "div[class*='job-card']",
                "div[class*='JobCard']",
                "article[class*='job']",
                "div[data-jobid]",
                "section[class*='job']",
                ".card-content",
                "div[class*='CardContent']"
            ]
            
            job_cards = []
            for selector in selectors:
                try:
                    job_cards = self.page.query_selector_all(selector)
                    if len(job_cards) > 3:  # Need at least a few jobs
                        print(f"      ✓ Found elements using selector: {selector}")
                        break
                except:
                    continue
            
            # If no jobs found with CSS, try to get all divs and filter
            if len(job_cards) < 3:
                print("      ⚠️  Primary selectors failed, trying alternative approach...")
                all_divs = self.page.query_selector_all("div")
                job_cards = []
                for div in all_divs:
                    try:
                        cls = div.get_attribute("class")
                        if cls and 'job' in cls.lower():
                            job_cards.append(div)
                    except:
                        continue
            
            print(f"      📌 Found {len(job_cards)} potential job cards")
            
            if len(job_cards) == 0:
                print("      ⚠️  No job cards found. Saving page for debugging...")
                with open("monster_debug.html", "w", encoding="utf-8") as f:
                    f.write(self.page.content())
                print("      💾 Page saved as monster_debug.html")
                return 0
            
            # Parse each job card
            for idx, card in enumerate(job_cards[:50], 1):  # Limit to first 50
                try:
                    job_data = self._parse_job_card(card)
                    if job_data and job_data.get('title') != "N/A":
                        # Check for duplicates
                        if not any(j['title'] == job_data['title'] and j['company'] == job_data['company'] 
                                  for j in self.jobs_data):
                            self.jobs_data.append(job_data)
                            jobs_found += 1
                except Exception as e:
                    continue
            
            return jobs_found
                    
        except Exception as e:
            print(f"      ❌ Error extracting jobs: {e}")
            return 0
    
    def _parse_job_card(self, card):
        """Parse individual job card to extract details"""
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
            title_selectors = ["h2", "h3", "h4", "[class*='title']", "[class*='Title']"]
            for selector in title_selectors:
                try:
                    elem = card.query_selector(selector)
                    if elem:
                        text = elem.inner_text().strip()
                        if text and len(text) > 3:
                            job['title'] = text
                            break
                except:
                    continue
            
            # Extract company
            company_selectors = ["[class*='company']", "[class*='Company']", "[data-company]"]
            for selector in company_selectors:
                try:
                    elem = card.query_selector(selector)
                    if elem:
                        text = elem.inner_text().strip()
                        if text and len(text) > 1:
                            job['company'] = text
                            break
                except:
                    continue
            
            # Extract location
            location_selectors = ["[class*='location']", "[class*='Location']"]
            for selector in location_selectors:
                try:
                    elem = card.query_selector(selector)
                    if elem:
                        text = elem.inner_text().strip()
                        if text and len(text) > 2:
                            job['location'] = text
                            break
                except:
                    continue
            
            # Extract salary
            salary_selectors = ["[class*='salary']", "[class*='Salary']", "[class*='pay']"]
            for selector in salary_selectors:
                try:
                    elem = card.query_selector(selector)
                    if elem:
                        text = elem.inner_text().strip()
                        if text and ('$' in text or 'USD' in text.upper()):
                            job['salary'] = text
                            break
                except:
                    continue
            
            # Extract URL
            try:
                link = card.query_selector("a")
                if link:
                    href = link.get_attribute('href')
                    if href:
                        if href.startswith('/'):
                            job['url'] = f"https://www.monster.com{href}"
                        elif 'monster.com' in href:
                            job['url'] = href
            except:
                pass
            
            # Extract description
            try:
                paragraphs = card.query_selector_all("p")
                for p in paragraphs:
                    text = p.inner_text().strip()
                    if len(text) > 30:
                        job['description'] = text[:200]
                        break
            except:
                pass
            
            return job
            
        except Exception as e:
            return job
    
    def _has_next_page(self):
        """Check if there's a next page button"""
        try:
            next_selectors = [
                "a[aria-label*='Next']",
                "button[aria-label*='Next']",
                "a[class*='next']",
                "[class*='pagination'] a:last-child"
            ]
            
            for selector in next_selectors:
                try:
                    btn = self.page.query_selector(selector)
                    if btn and btn.is_enabled():
                        return True
                except:
                    continue
            return False
        except:
            return False
    
    def close(self):
        """Close the browser"""
        try:
            if hasattr(self, 'context'):
                self.context.close()
            if hasattr(self, 'browser'):
                self.browser.close()
            if hasattr(self, 'playwright'):
                self.playwright.stop()
            print("✓ Browser closed")
        except:
            pass


def scrape_monster_jobs(query, location="India"):
    scraper = MonsterScraper(headless=True)
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
                "source": "Monster"
            }
            standardized_jobs.append(standardized_job)
        
        return standardized_jobs
    finally:
        scraper.close()


# Main execution
if __name__ == "__main__":
    print("\n" + "="*60)
    print("MONSTER.COM JOB SCRAPER (PLAYWRIGHT VERSION)")
    print("="*60 + "\n")
    
    # Get search parameters from user
    job_role = input("Enter Job Role (e.g. Python Developer): ")
    job_location = input("Enter Location (e.g. India or Remote): ")
    
    if not job_role:
        job_role = "Python Developer"
    if not job_location:
        job_location = "India"

    jobs = scrape_monster_jobs(job_role, job_location)
    
    if jobs:
        print(f"\n✅ Scraped {len(jobs)} jobs successfully!")
        for j in jobs[:3]:
            print(f"- {j['title']} at {j['company']}")
    else:
        print("\n❌ No jobs found.")