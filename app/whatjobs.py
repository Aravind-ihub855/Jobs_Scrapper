from playwright.sync_api import sync_playwright
import time
import re

def slugify(text: str) -> str:
    """Converts a string to a slug (e.g., 'Freshers Data' -> 'freshers-data')."""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    text = re.sub(r'\s+', '-', text)
    return text.strip("-")

def scrape_whatjobs_jobs(query, location=None):
    extracted_jobs = []
    
    # Construct URL. WhatJobs uses path-based queries like /jobs/fresher-big-data
    # If location is provided, it might optionally be added, but user example only showed query.
    # We will stick to the basic query URL for now: https://en-in.whatjobs.com/jobs/{query}
    # Location filtering usually works via query params or separate path, but sticky to user URL pattern.
    
    base_url = "https://en-in.whatjobs.com/jobs"
    query_slug = slugify(query)
    search_url = f"{base_url}/{query_slug}"
    
    # Add location param if needed? 
    # The user provided: https://en-in.whatjobs.com/jobs/fresher-big-data?pD=0&aT=0
    # Let's verify if location can be added. 
    # For now, we will just use the query slug.
    
    print(f"Scraping WhatJobs URL: {search_url}")

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        try:
            page.goto(search_url, timeout=60000)
            page.wait_for_selector(".ajCard", timeout=15000)
            
            # Handle potential popups (WhatJobs has cookie/alert popups often)
            try:
                page.click("button:has-text('Accept')", timeout=2000)
            except:
                pass

            # Get all job cards
            cards = page.query_selector_all(".ajCard")
            print(f"Found {len(cards)} cards on the page.")

            for i, card in enumerate(cards):
                try:
                    card.scroll_into_view_if_needed()
                    
                    # 1. Title
                    title_el = card.query_selector(".jobTitle")
                    title = title_el.inner_text().strip() if title_el else "N/A"
                    
                    # 2. Company & Location (Fixing the xpath error)
                    # We can use evaluate to get the parent's text directly
                    company = "N/A"
                    company_icon = card.query_selector(".companyName")
                    if company_icon:
                        # Get text of the parent element
                        company = company_icon.evaluate("el => el.parentElement.innerText").strip()

                    location_text = "N/A"
                    loc_icon = card.query_selector(".location")
                    if loc_icon:
                        location_text = loc_icon.evaluate("el => el.parentElement.innerText").strip()

                    # 3. Salary
                    salary = "N/A"
                    salary_el = card.query_selector(".aiSalary")
                    if salary_el:
                         # The salary text is often inside this element mixed with icons, inner_text handles it well
                        salary = salary_el.inner_text().strip()

                    # 4. Description
                    # Strategy: Try to get text content first (works even if hidden)
                    description = "N/A"
                    desc_el = card.query_selector(".ajCardDetails") or card.query_selector(".jDesc")
                    
                    if desc_el:
                        # text_content gets text even if element is hidden (display: none)
                        raw_desc = desc_el.text_content().strip()
                        if len(raw_desc) > 100:
                            description = raw_desc
                            # Clean up potential "Tap Again To Close" text
                            description = description.replace("Tap Again To Close", "").strip()
                            description = description.replace("Job Description", "").strip()

                    # If description is still missing or too short, try expanding
                    if description == "N/A" or len(description) < 100:
                        is_expanded = card.get_attribute("data-expanded")
                        if is_expanded != "true":
                            # Click to expand
                            time.sleep(0.5) 
                            try:
                                card.click(timeout=3000)
                                page.wait_for_timeout(1000)
                                # Re-grab description after expansion
                                if desc_el:
                                     description = desc_el.inner_text().strip()
                            except Exception as click_err:
                                print(f"Click failed for card {i}, skipping expansion: {click_err}")
                                # Fallback to whatever we had
                        
                    # 6. Job ID (from attribute)
                    job_id = card.get_attribute("data-id") or f"whatjobs-{i}"
                    job_link = f"{search_url}?id={job_id}"

                    job_data = {
                        "title": title,
                        "company": company,
                        "location": location_text,
                        "job_description": description[:500] + "..." if len(description) > 500 else description, # Truncate for log if needed, but store full
                        "job_url": job_link,
                        "salary": salary,
                        "job_board": "whatjobs",
                        "post_date": "N/A" 
                    }
                    
                    # Store full description in the object
                    job_data["job_description"] = description
                    
                    extracted_jobs.append(job_data)
                    print(f"Scraped: {title} at {company}")
                    
                except Exception as e:
                    print(f"Error scraping card {i}: {e}")
                    continue


        except Exception as e:
            print(f"Error scraping WhatJobs: {e}")
        finally:
            browser.close()

    return extracted_jobs
