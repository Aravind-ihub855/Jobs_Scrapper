from playwright.sync_api import sync_playwright
import time
import random
import re

def scrape_naukri_jobs(query, location=None, max_pages=10):
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
            # max_pages is now a parameter
            
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
                        try:
                            # 1. Try finding by icon then sibling span (most reliable)
                            exp_span = job_page.query_selector("i.ni-icon-bag + span") or \
                                       job_page.query_selector("i.ni-icon-bag + [class*='exp'] span")
                            if exp_span:
                                experience = exp_span.inner_text().strip()
                            
                            if experience == "N/A":
                                # 2. Try container
                                exp_container = job_page.query_selector("[class*='exp']")
                                if exp_container:
                                    experience = exp_container.inner_text().strip()
                        except: pass

                        if experience == "N/A":
                             # Fallback
                             exp_el = job_page.query_selector("[class*='exp'] span") or \
                                      job_page.query_selector(".exp")
                             if exp_el:
                                 experience = exp_el.inner_text().strip()
                             
                        # Salary
                        salary = "N/A"
                        try:
                            # 1. Try finding by icon then sibling span (from screenshot)
                            sal_span = job_page.query_selector("i.ni-icon-salary + span") or \
                                       job_page.query_selector("i.ni-icon-salary + [class*='salary'] span")
                            if sal_span:
                                salary = sal_span.inner_text().strip()
                            
                            if salary == "N/A":
                                # 2. Try container (from screenshot: styles_jhc__salary__jdfEC)
                                sal_container = job_page.query_selector("[class*='salary']")
                                if sal_container:
                                    salary = sal_container.inner_text().strip()
                        except: pass
                        
                        if salary == "N/A":
                            # Fallback but be careful not to grab experience
                            sal_el = job_page.query_selector("li:has-text('PA')") or \
                                     job_page.query_selector("li:has-text('Disclosed')") 
                                     
                            # Removed .salary as it matches footer/sidebar junk
                            
                            if sal_el:
                                salary = sal_el.inner_text().strip()
                        
                        # Validate Salary: If it's too long or has newlines, it's likely a menu/junk
                        if len(salary) > 50 or '\n' in salary:
                             salary = "N/A"


                        # Description and Metadata
                        description = "N/A"
                        key_skills = []
                        metadata = {}

                        # Try to find the description container
                        desc_el = job_page.query_selector(".dang-inner-html") or \
                                  job_page.query_selector("[class*='job-desc']") or \
                                  job_page.query_selector("#job-description")
                        
                        if desc_el:
                            description = desc_el.inner_text().strip()
                        
                        # Extract Key Skills as an array
                        try:
                            # Naukri chips for skills
                            skill_chips = job_page.query_selector_all("a[class*='chip']") or \
                                          job_page.query_selector_all(".key-skill a") or \
                                          job_page.query_selector_all(".skills-container a")
                            
                            if skill_chips:
                                for chip in skill_chips:
                                    skill_text = chip.inner_text().strip()
                                    if skill_text and skill_text not in key_skills:
                                        key_skills.append(skill_text)
                        except: pass

                        # Extract other details (Role, Industry, etc.)
                        try:
                            # Usually in labels followed by values
                            # Or in a specific details section
                            detail_labels = job_page.query_selector_all("label")
                            for label in detail_labels:
                                label_text = label.inner_text().strip().replace(":", "")
                                if any(k in label_text for k in ["Role", "Industry Type", "Department", "Employment Type", "Education"]):
                                    # Value is usually next sibling or in same parent
                                    try:
                                        val = label.evaluate("el => el.nextElementSibling ? el.nextElementSibling.innerText : ''")
                                        if not val:
                                            # Fallback: check index in parent
                                            val = label.evaluate("el => el.parentElement.innerText.replace(el.innerText, '').strip()")
                                        
                                        if val and len(val) < 200: # Sanity check
                                            metadata[label_text] = val.strip()
                                    except: pass
                        except: pass
                        
                        # Post Date
                        post_date = "N/A"
                        # From screenshot: label "Posted:" sibling span
                        # Selector: label:has-text("Posted:") + span
                        try:
                            # Try finding the label first
                            posted_label = job_page.locator("label:has-text('Posted:')")
                            if posted_label.count() > 0:
                                # Get the next sibling span
                                date_span = posted_label.locator("xpath=following-sibling::span").first
                                if date_span.is_visible():
                                    post_date = date_span.inner_text().strip()
                        except: pass
                        
                        if post_date == "N/A":
                            # Fallback to the previous class selector if specific one fails
                            date_el = job_page.query_selector(".job-post-day") or \
                                      job_page.query_selector("[class*='stat'] span")
                            if date_el:
                                post_date = date_el.inner_text().strip()
                        

                        # Clean description to remove redundant footer (Role, Industry, etc. and Key Skills)
                        # These are often preceded by "read more" or just appear at the end.
                        if description != "N/A":
                             # Remove "read more" and everything after it
                             if "read more" in description.lower():
                                 description = re.split(r"read more", description, flags=re.IGNORECASE)[0].strip()
                             
                             # Remove Role/Industry footer if it exists and we've already extracted it
                             if "Role:" in description:
                                 description = description.split("Role:")[0].strip()

                        job_data = {
                            "title": title,
                            "company": company,
                            "location": location_text,
                            "experience": experience,
                            "salary": salary,
                            "job_description": description,
                            "key_skills": key_skills,
                            "metadata": metadata,
                            "job_url": job_url,
                            "job_board": "naukri",
                            "post_date": post_date,
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
                print("Checking for next button...")
                
                # Scroll to bottom to ensure "Next" button is loaded and visible
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2) # Wait for potential dynamic content
                
                # Close potential privacy banner first
                try: 
                    blocker = page.query_selector("button:has-text('Got it')")
                    if blocker and blocker.is_visible():
                        blocker.click()
                        time.sleep(0.5)
                except: pass

                try:
                    # Try specific class first if known, then text match
                    # Class might change, but "Next" text is usually consistent
                    next_btn = page.query_selector("a.styles_btn-secondary__2AsIP:has-text('Next')") or \
                               page.query_selector("a:has-text('Next')") or \
                               page.query_selector("button:has-text('Next')") or \
                               page.query_selector(".styles_btn-secondary__2AsIP")
                    
                    if next_btn and next_btn.is_visible():
                        # Check disabled state
                        # Naukri uses 'disabled' attribute or class
                        is_disabled = next_btn.get_attribute("disabled") is not None
                        classes = next_btn.get_attribute("class") or ""
                        
                        if is_disabled or "disabled" in classes.lower() or "previous" in classes.lower():
                            print("Next button found but disabled or is 'Previous' button. Optimization loop finished.")
                            break
                        
                        print("Navigating to next page...")
                        # Use force=True to bypass potential overlays
                        # Also use JS click as a fallback if Playwright click fails
                        try:
                            next_btn.click(force=True, timeout=10000)
                        except:
                            next_btn.evaluate("el => el.click()")

                        # Wait for page navigation or content update
                        # domcontentloaded is more reliable than networkidle for sites with heavy trackers
                        try:
                            page.wait_for_load_state("domcontentloaded", timeout=30000)
                        except: pass
                        
                        # Wait specifically for results to refresh
                        time.sleep(random.uniform(3, 5))
                        page_num += 1
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