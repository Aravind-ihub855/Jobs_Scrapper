from playwright.sync_api import sync_playwright
import time
from urllib.parse import quote_plus

BASE_URL = "https://www.simplyhired.com/search?q={query}&l="

def scrape_simplyhired_jobs(search_query: str):
    encoded_query = quote_plus(search_query)
    url = BASE_URL.format(query=encoded_query)

    jobs = []

    with sync_playwright() as p:
        # Launch browser (headless=True as per typical server requirements, 
        # though reference used False. Keeping True for stability in background)
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        try:
            print(f"Navigating to {url}")
            page.goto(url, timeout=60000)
            
            # Helper to scroll to bottom to load more jobs (SimplyHired often uses infinite scroll)
            # Adapting the reference style logic but for scrolling
            last_height = page.evaluate("document.body.scrollHeight")
            while True:
                page.mouse.wheel(0, 5000)
                time.sleep(2) # Wait for content to load
                new_height = page.evaluate("document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            # Use locators as per reference
            job_cards = page.locator("div[data-testid='searchSerpJob']").all()
            
            if not job_cards:
                print("No job listings found on the page")

            for card in job_cards:
                try:
                    # Scroll card into view to ensure we can interact
                    card.scroll_into_view_if_needed()
                    
                    # Title & Link
                    title_elem = card.locator("h2[data-testid='searchSerpJobTitle'] > a")
                    if title_elem.count() > 0:
                        title = title_elem.inner_text().strip()
                        href = title_elem.get_attribute("href")
                        job_url = f"https://www.simplyhired.com{href}" if href else None
                    else:
                        title = "N/A"
                        job_url = None

                    # Company
                    company_elem = card.locator("span[data-testid='companyName']")
                    company = company_elem.inner_text().strip() if company_elem.count() > 0 else "N/A"

                    # Location
                    location_elem = card.locator("span[data-testid='searchSerpJobLocation']")
                    location = location_elem.inner_text().strip() if location_elem.count() > 0 else "N/A"

                    # Initial Salary (from card)
                    salary_elem = card.locator("span[data-testid^='salaryChip']")
                    salary = salary_elem.inner_text().strip() if salary_elem.count() > 0 else "N/A"

                    # --- Click to load details in side pane ---
                    if title_elem.count() > 0:
                        title_elem.click()
                        time.sleep(2) # Wait for panel to switch

                        # Locate the right-side details pane.
                        # We use the unique "Apply" button or similar unique element in that pane anchor.
                        # SimplyHired usually has an "Apply Now" or "Quick Apply" button in the right pane header.
                        details_pane = page.locator("aside").first
                        if not details_pane.count() > 0:
                            # Fallback: look for a fixed position container or the one containing the description
                            details_pane = page.locator("div[class*='Fixed'], div[class*='Sticky']").last 

                        # Retry finding the pane by content if generic structure fails
                        if not details_pane.is_visible():
                             try:
                                 # Find the container that holds the "Full Job Description" header
                                 header = page.locator("h2", has_text="Full Job Description").first
                                 if header.count() > 0:
                                     # Go up until we hit the scrollable container (often has 'overflow-y', but we can just use the parent)
                                     # For now, let's just use the page scroll or focus on the element.
                                     # Actually, simplyhired splits view: Left is list, Right is details.
                                     # We will try to scroll the 'window' is sometimes enough if the separate scroll isn't captured?
                                     # No, usually need to hover and wheel or find the scrollable div.
                                     pass
                             except:
                                 pass

                        # Explicitly try to scroll the element that contains the description
                        try:
                            # Focus on the description header and scroll down
                            desc_header_indicator = page.locator("h2", has_text="Full Job Description").first
                            if desc_header_indicator.count() > 0:
                                # Scroll this container into view -> then scroll the container itself.
                                # Often simplest to click/hover and keyboard page down or mouse wheel
                                desc_header_indicator.scroll_into_view_if_needed()
                                
                                # Method: Mouse wheel on the pane
                                box = desc_header_indicator.bounding_box()
                                if box:
                                    page.mouse.move(box["x"], box["y"])
                                    for _ in range(5): # Scroll down a few times
                                        page.mouse.wheel(0, 500)
                                        time.sleep(0.5)
                        except Exception as e:
                            print(f"Scrolling error: {e}")

                        time.sleep(1) # Wait for lazy load

                    # --- Scrape Detailed View ---
                    
                    # 1. Full Job Description
                    description = "N/A"
                    # Robust Strategy: Find header "Full Job Description", get all text following it up to the end or next section?
                    # SimplyHired has a specific div for this usually.
                    # We'll try specific selectors first, then text-based fallbacks.
                    
                    # Try the standard Vercel/Next.js style class if available, else generic.
                    # Look for the container that *contains* the text "Full Job Description" and is a sibling of the header?
                    # Usually: <h2>Full Job Description</h2> <div> ... text ... </div>
                    
                    desc_header = page.locator("h2", has_text="Full Job Description").first
                    if desc_header.count() > 0:
                        # Assumption: Description is in the next sibling div or the parent's next sibling
                        # We can grab the whole parent text if it's the main container
                        # Let's try grabbing the div immediately following the header
                        container = desc_header.locator("xpath=following-sibling::div").first
                        if container.count() > 0:
                            description = container.inner_text().strip()
                        else:
                            # Maybe it's inside the same parent?
                            description = desc_header.locator("..").inner_text().strip()
                            # Clean up: remove the header text itself
                            description = description.replace("Full Job Description", "").strip()

                    # 2. Qualifications
                    # Header: "Qualifications"
                    qualifications = []
                    qual_header = page.locator("h2", has_text="Quarterifications").first # typo check? No, "Qualifications"
                    # Actually check for "Qualifications" OR "Requirements"
                    qual_header = page.locator("h2", has_text="Qualifications").first
                    if qual_header.count() == 0:
                         qual_header = page.locator("h2", has_text="Requirements").first

                    if qual_header.count() > 0:
                        # Usually a list (ul) or chips (divs/spans) follow
                        # Try finding ul first
                        ul = qual_header.locator("xpath=following-sibling::ul").first
                        if ul.count() > 0:
                            qualifications = [li.inner_text().strip() for li in ul.locator("li").all()]
                        else:
                            # Try div with chips
                            # Grab next div
                            next_div = qual_header.locator("xpath=following-sibling::div").first
                            if next_div.count() > 0:
                                # Check for chips
                                chips = next_div.locator("span").all()
                                if chips:
                                    qualifications = [c.inner_text().strip() for c in chips if len(c.inner_text().strip()) > 1]
                                else:
                                    # Just text lines
                                    txt = next_div.inner_text()
                                    qualifications = [t.strip() for t in txt.split('\n') if t.strip()]

                    # 3. Job Type (and other Details)
                    # Header: "Job Details"
                    job_type = "N/A"
                    details_header = page.locator("h2", has_text="Job Details").first
                    if details_header.count() > 0:
                        # content usually in following div
                        det_container = details_header.locator("xpath=following-sibling::div").first
                        if det_container.count() > 0:
                            text = det_container.inner_text()
                            # Extract Type
                            if "Full-time" in text: job_type = "Full-time"
                            elif "Part-time" in text: job_type = "Part-time"
                            elif "Contract" in text: job_type = "Contract"
                            elif "Temporary" in text: job_type = "Temporary"
                            elif "Internship" in text: job_type = "Internship"
                            else:
                                # Fallback: take the first line roughly
                                lines = text.split('\n')
                                if lines: job_type = lines[0]

                    job = {
                        "keyword": search_query,
                        "title": title,
                        "company": company,
                        "location": location,
                        "salary": salary,
                        "job_type": job_type,
                        "qualifications": qualifications,
                        "job_description": description,
                        "job_url": job_url,
                        "source": "SimplyHired"
                    }
                    
                    jobs.append(job)

                except Exception as e:
                    print(f"Error processing individual job: {e}")
                    continue
            
        except Exception as e:
            print(f"Scraping error: {e}")
            # Optional: Capture screenshot on error for debugging
            # page.screenshot(path="error_screenshot.png")
        finally:
            browser.close()

    return jobs
