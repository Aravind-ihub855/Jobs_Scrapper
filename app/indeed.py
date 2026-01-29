from playwright.sync_api import sync_playwright
import time
import random
from urllib.parse import quote_plus

class IndeedScraper:
    def __init__(self, headless=False):
        """
        Initialize Indeed scraper (India version)
        """
        self.jobs_data = []
        self.headless = headless
        self.base_url = "https://in.indeed.com/jobs"

    def search_jobs(self, keywords, location, max_pages=1, freshness=None):
        """
        Search for jobs on Indeed India
        """
        print(f"\n{'='*70}")
        print(f"INDEED INDIA JOB SCRAPER")
        print(f"{'='*70}")
        print(f"Search: {keywords}")
        print(f"Location: {location}")
        print(f"Freshness: {freshness} days")
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
                q = quote_plus(keywords)
                l = quote_plus(location) if location else ""
                
                url_params = f"q={q}&l={l}"
                if freshness:
                    url_params += f"&fromage={freshness}"
                
                search_url = f"{self.base_url}?{url_params}"
                
                for page_num in range(max_pages):
                    start = page_num * 10
                    current_url = f"{search_url}&start={start}"
                    
                    print(f"\nScraping page {page_num + 1}...")
                    print(f"   Link: {current_url}")
                    
                    try:
                        page.goto(current_url, timeout=60000, wait_until="domcontentloaded")
                        # Handle potential cookie banner or popup
                        try:
                            page.wait_for_selector("button#onetrust-accept-btn-handler", timeout=5000)
                            page.click("button#onetrust-accept-btn-handler")
                        except:
                            pass

                        # Wait for job listings or "no jobs" message
                        page.wait_for_selector(".jobsearch-ResultsList, .job_seen_beacon, .no-results", timeout=15000)
                        
                        if page.query_selector(".no-results"):
                            print("   No more jobs found.")
                            break
                            
                    except Exception as e:
                        print(f"     Error loading page {page_num + 1}: {e}")
                        break

                    # Extract job details using split-view
                    job_cards = page.locator(".job_seen_beacon").all()
                    if not job_cards:
                        print("    No job cards found on this page.")
                        break
                    
                    print(f"   Found {len(job_cards)} job cards. Extracting details...")
                    
                    for idx, card in enumerate(job_cards, 1):
                        try:
                            # 1. Click the card to load details in right pane
                            # Ensure it's in view and clickable
                            card.scroll_into_view_if_needed()
                            try:
                                card.locator("h2.jobTitle").click(timeout=5000)
                            except:
                                # Fallback click
                                card.click(force=True, timeout=5000)
                                
                            time.sleep(random.uniform(1.5, 2.5)) # Wait for pane to load
                            
                            # 2. Extract from card (Basic info)
                            title_el = card.locator("h2.jobTitle span[title]").first or card.locator("h2.jobTitle").first
                            title = title_el.get_attribute("title") or title_el.inner_text().strip()
                            company = "N/A"
                            company_el = card.locator("span[data-testid='company-name']")
                            if company_el.count() > 0:
                                company = company_el.inner_text().strip()
                                
                            loc = "N/A"
                            loc_el = card.locator("div[data-testid='text-location']")
                            if loc_el.count() > 0:
                                loc = loc_el.inner_text().strip()
                                
                            salary = "N/A"
                            salary_el = card.locator("div.salary-snippet-container, div.metadata.salary-snippet-container")
                            if salary_el.count() > 0:
                                salary = salary_el.inner_text().strip()
                                
                            posted = "N/A"
                            posted_el = card.locator("span.date, span.myJobsState")
                            if posted_el.count() > 0:
                                posted = posted_el.inner_text().strip()
                                
                            job_url = "N/A"
                            link_el = card.locator("h2.jobTitle a").first
                            if link_el.count() > 0:
                                href = link_el.get_attribute("href")
                                full_url = "https://in.indeed.com" + href if href.startswith("/") else href
                                
                                # Normalize URL by extracting 'jk' (Job Key) for stable duplicate prevention
                                import re
                                jk_match = re.search(r"jk=([a-zA-Z0-9]+)", full_url)
                                if jk_match:
                                    jk = jk_match.group(1)
                                    job_url = f"https://in.indeed.com/viewjob?jk={jk}"
                                else:
                                    job_url = full_url

                            # 3. Extract from Detail Pane (Description)
                            description = "N/A"
                            desc_pane = page.locator("#jobDescriptionText")
                            if desc_pane.count() > 0:
                                description = desc_pane.inner_text().strip()
                            
                            # 4. Extract Job Type and Salary from detail pane with improved selectors
                            job_type = "N/A"
                            # Try specific aria-label first
                            type_el = page.locator("div[aria-label*='Job type']").first
                            if type_el.count() > 0:
                                # Often contains "Job type" header, we want the value
                                type_text = type_el.inner_text().strip().replace("Job type", "").strip()
                                if type_text:
                                    job_type = type_text.split("\n")[0] # Get first line if multiple

                            # Fallback if still N/A or empty
                            if job_type == "N/A" or not job_type:
                                type_el = page.locator("div#jobDetailsSection div:has-text('Job type') + div").first
                                if type_el.count() > 0:
                                    job_type = type_el.inner_text().strip()

                            # Salary refinement
                            salary_pane = page.locator("div[aria-label*='Pay'], div[aria-label*='Salary']").first
                            if salary_pane.count() > 0:
                                salary_text = salary_pane.inner_text().strip()
                                # Clean up common headers
                                for word in ["Pay", "Salary", "Estimated"]:
                                    salary_text = salary_text.replace(word, "")
                                salary_text = salary_text.strip()
                                if salary_text:
                                    salary = salary_text.split("\n")[0]

                            # 5. Regex Fallback from Description (Very common for Indeed India)
                            import re
                            if (salary == "N/A" or "₹" not in salary) and description != "N/A":
                                # Look for patterns like Pay: ₹15,000 - ₹25,000
                                salary_match = re.search(r"(?:Pay|Salary|Compensation|Starts from):\s*(₹?[\d,.\s-]+(?:per month|a month|per year|a year)?)", description, re.IGNORECASE)
                                if salary_match:
                                    salary = salary_match.group(1).strip()
                            
                            if (job_type == "N/A" or not job_type) and description != "N/A":
                                type_match = re.search(r"Job Type:\s*([^\n\r]+)", description, re.IGNORECASE)
                                if type_match:
                                    job_type = type_match.group(1).strip()

                            job_data = {
                                "title": title,
                                "company": company,
                                "location": loc,
                                "salary": salary,
                                "posted_date": posted,
                                "job_type": job_type,
                                "description": description,
                                "url": job_url
                            }
                            
                            self.jobs_data.append(job_data)
                            print(f"      [{idx}/{len(job_cards)}] Scraped: {title[:40]}...")

                        except Exception as e:
                            print(f"      Failed to scrape job card {idx}: {e}")

                    # Check for Next Button
                    next_btn = page.locator("a[data-testid='pagination-page-next']")
                    if next_btn.count() == 0:
                        print("   No next page found.")
                        break
                        
                    time.sleep(random.uniform(2, 4))
            
            except Exception as e:
                print(f"Error during scraping: {e}")
            finally:
                browser.close()

def scrape_indeed_jobs(query, location="India", max_pages=1, freshness=None):
    scraper = IndeedScraper(headless=False)
    try:
        scraper.search_jobs(query, location, max_pages, freshness)
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
                "source": "Indeed"
            })
        return results
    except Exception as e:
        print(f"Global Scrape Error: {e}")
        return []

if __name__ == "__main__":
    q = "Python Developer"
    l = "Coimbatore"
    jobs = scrape_indeed_jobs(q, l, max_pages=1, freshness=1)
    print(f"\nScraped {len(jobs)} jobs.")
