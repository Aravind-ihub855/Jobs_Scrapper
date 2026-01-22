from playwright.sync_api import sync_playwright
import time
import random
import re

def scrape_naukri_jobs(query, location=None):
    extracted_jobs = []
    
    # Construct URL
    # Use generic generic valid format: https://www.naukri.com/{slug}-jobs?k={query}&l={location}
    # This avoids 404s when a specific "slug-in-location" page doesn't exist.
    query_slug = query.lower().replace(" ", "-")
    query_param = query.replace(" ", "%20")
    
    base_url = f"https://www.naukri.com/{query_slug}-jobs"
    search_url = f"{base_url}?k={query_param}"
    
    if location:
        location_param = location.replace(" ", "%20")
        search_url += f"&l={location_param}"
    
    print(f"Scraping Naukri URL: {search_url}")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            viewport={'width': 1366, 'height': 768},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            extra_http_headers={
                'Referer': 'https://www.naukri.com/',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        )
        page = context.new_page()

        try:
            page.goto(search_url, timeout=60000)
            
            # Handling "Maybe later" or login popups if they appear
            try:
                page.wait_for_selector(".srp-jobtuple-wrapper", timeout=20000)
            except:
                print("Could not find job list. Maybe no results or anti-bot check.")
                return []

            # Pagination Loop
            page_num = 1
            max_pages = 2 # Reduced for testing speed
            
            while page_num <= max_pages:
                print(f"Scraping Search Page {page_num}...")
                
                # Get all job links
                job_tuples = page.query_selector_all(".srp-jobtuple-wrapper")
                page_job_urls = []
                
                for card in job_tuples:
                    try:
                        title_link = card.query_selector("a.title")
                        if title_link:
                            href = title_link.get_attribute("href")
                            if href:
                                page_job_urls.append(href)
                    except:
                        continue
                
                print(f"Found {len(page_job_urls)} jobs on page {page_num}.")
                
                # Visit each job URL
                for job_url in page_job_urls:
                    try:
                        print(f"Visiting job: {job_url}")
                        job_page = context.new_page()
                        job_page.goto(job_url, timeout=30000)
                        job_page.wait_for_load_state("domcontentloaded")
                        
                        # Check for 404
                        page_title = job_page.title()
                        if "404" in page_title or "not found" in page_title.lower():
                             print("  -> Job page returned 404/Not Found.")
                             job_page.close()
                             continue

                        # Extract Details using Partial Class Selectors (Robust to hashing)
                        
                        # Title
                        title = "N/A"
                        # h1 is usually safe, fallback to class containing 'header-title'
                        if job_page.query_selector("h1"):
                            title = job_page.inner_text("h1").strip()
                        elif job_page.query_selector("[class*='jd-header-title']"):
                             title = job_page.inner_text("[class*='jd-header-title']").strip()
                        elif job_page.query_selector(".job-title"):
                             title = job_page.inner_text(".job-title").strip()
                        
                        # Company
                        company = "N/A"
                        # class usually contains 'comp-name'
                        comp_el = job_page.query_selector("[class*='jd-header-comp-name'] a") or \
                                  job_page.query_selector("[class*='jd-header-comp-name']") or \
                                  job_page.query_selector(".comp-name")
                        if comp_el:
                            company = comp_el.inner_text().strip()
                            
                        # Location
                        location_text = "N/A"
                        # class contains 'location'
                        loc_el = job_page.query_selector("[class*='location'] a") or \
                                 job_page.query_selector("[class*='location']") or \
                                 job_page.query_selector(".loc")
                        if loc_el:
                            location_text = loc_el.inner_text().strip()
                            
                        # Experience
                        experience = "N/A"
                        # class contains 'exp'
                        exp_el = job_page.query_selector("[class*='exp'] span") or \
                                 job_page.query_selector("[class*='exp']") or \
                                 job_page.query_selector(".exp")
                        if exp_el:
                            experience = exp_el.inner_text().strip()
                            
                        # Salary
                        salary = "N/A"
                        # class contains 'salary'
                        sal_el = job_page.query_selector("[class*='salary'] span") or \
                                 job_page.query_selector("[class*='salary']") or \
                                 job_page.query_selector(".salary")
                        if sal_el:
                            salary = sal_el.inner_text().strip()
                            
                        # Description
                        description = "N/A"
                        # class contains 'job-desc'
                        desc_el = job_page.query_selector("[class*='job-desc']") or \
                                  job_page.query_selector(".dang-inner-html") or \
                                  job_page.query_selector("#job-description")
                        if desc_el:
                            description = desc_el.inner_text().strip()
                        
                        job_data = {
                            "title": title,
                            "company": company,
                            "location": location_text,
                            "experience": experience,
                            "salary": salary,
                            "job_description": description,
                            "job_url": job_url,
                            "job_board": "naukri",
                            "post_date": "N/A"
                        }
                        
                        extracted_jobs.append(job_data)
                        print(f"  -> Extracted: {title} at {company}")
                        
                        job_page.close()
                        time.sleep(random.uniform(1, 2))
                        
                    except Exception as e:
                        print(f"  -> Error visiting job: {e}")
                        try: job_page.close() 
                        except: pass
                        continue

                # Check for Next Button
                # Selector: a.mw-25.btn-next usually.
                # Use a specific selector to avoid matching random text.
                # Check for Next Button
                print("Checking for next button...")
                
                # Close potential privacy banner first
                try: 
                    blocker = page.query_selector("button:has-text('Got it')")
                    if blocker and blocker.is_visible():
                        blocker.click()
                        time.sleep(0.5)
                except: pass

                # Robust selector for Next button: 
                # 1. Contains text "Next"
                # 2. Is an 'a' tag (usually) or button
                # 3. Not disabled
                try:
                    # Generic text match is safest because class names like 'styles_btn-secondary__2AsIP' change often.
                    # We check visible 'Next' buttons.
                    next_btn = page.query_selector("a:has-text('Next')") or page.query_selector("button:has-text('Next')")
                    
                    if next_btn and next_btn.is_visible():
                        # Check disabled state
                        # Naukri uses 'disabled' attribute or class
                        is_disabled = next_btn.get_attribute("disabled") is not None
                        classes = next_btn.get_attribute("class") or ""
                        
                        if is_disabled or "disabled" in classes.lower() or "previous" in classes.lower():
                            # If we matched 'Next' text but it's actually disabled or weirdly the previous button (unlikely with has-text Next)
                            print("Next button found but disabled. Optimization loop finished.")
                            break
                        
                        print("Navigating to next page...")
                        
                        # Scroll into view with margin to avoid sticky header
                        next_btn.scroll_into_view_if_needed()
                        page.evaluate("window.scrollBy(0, -100)") # Scroll up a bit so it's not under header/footer
                        time.sleep(1)
                        
                        # Force click with JS to bypass overlays
                        next_btn.evaluate("e => e.click()")
                        
                        time.sleep(5) # Wait for potential SPA transition or reload
                        page_num += 1
                        page.wait_for_load_state("domcontentloaded")
                    else:
                        print("No next button found. Optimization loop finished.")
                        break
                        
                except Exception as e:
                     print(f"Pagination error: {e}")
                     break
                    
        except Exception as e:
            print(f"Error scraping Naukri search page: {e}")
            
        finally:
            browser.close()

    return extracted_jobs