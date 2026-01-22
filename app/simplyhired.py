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

                        # --- SCROLLING LOGIC ---
                        # We need to scroll the separate details pane, not the main window.
                        # Strategy: Hover over the "Quick Apply" / "Apply Now" button area (top of pane)
                        # and then wheel down.
                        try:
                            # Anchor: The Apply button is usually sticky or at the top of the right pane
                            apply_button = page.locator("a:has-text('Quick Apply'), button:has-text('Quick Apply'), a:has-text('Apply Now'), button:has-text('Apply Now')").first
                            
                            if apply_button.count() > 0 and apply_button.is_visible():
                                # Hover over the center of the pane (slightly below the apply button)
                                box = apply_button.bounding_box()
                                if box:
                                    # Move mouse to the middle of the pane (horizontally) and below the button
                                    # Assuming pane is roughly 600px wide, allow offset
                                    page.mouse.move(box["x"], box["y"] + 100)
                                    
                                    # Scroll down multiple times to trigger lazy loading
                                    for _ in range(10): 
                                        page.mouse.wheel(0, 500)
                                        time.sleep(0.2)
                            else:
                                # Fallback: Hover over "Job Details" header if visible
                                jd_header = page.locator("h2", has_text="Job Details").first
                                if jd_header.count() > 0:
                                    jd_header.hover()
                                    for _ in range(10): 
                                        page.mouse.wheel(0, 500)
                                        time.sleep(0.2)
                                        
                        except Exception as e:
                            print(f"Scrolling error: {e}")

                        time.sleep(1) # Wait for content to settle

                    # --- Scrape Detailed View ---
                    
                    # --- Scrape Detailed View ---
                    
                    def safe_get_text(locator):
                        try:
                            if locator.count() > 0:
                                return locator.inner_text().strip()
                        except:
                            pass
                        return "N/A"

                    # Robust extraction helper
                    def get_section_content(header_text):
                        # Relaxed: Try standard headers first, then generic text matches
                        # We use a union selector or try-catch sequence
                        
                        # 1. Try Header Tags
                        header = page.locator(f"h2:has-text('{header_text}'), h3:has-text('{header_text}'), h4:has-text('{header_text}')").first
                        
                        # 2. If not found, try generic bold/strong or div with specific text
                        if header.count() == 0:
                            header = page.locator(f"div:has-text('{header_text}'), span:has-text('{header_text}'), strong:has-text('{header_text}')").filter(has_text=header_text).last
                        
                        if header.count() == 0:
                            return None

                        # Strategy 1: Immediate Sibling
                        sibling = header.locator("xpath=following-sibling::div").first
                        if sibling.count() > 0 and len(sibling.inner_text().strip()) > 0:
                            return sibling
                        
                        # Strategy 2: Parent's Sibling (Header wrapped in div)
                        parent_sibling = header.locator("xpath=../following-sibling::div").first
                        if parent_sibling.count() > 0 and len(parent_sibling.inner_text().strip()) > 0:
                            return parent_sibling
                        
                        # Strategy 3: Just the next element in DOM
                        next_elem = header.locator("xpath=following-sibling::*[1]").first
                        if next_elem.count() > 0:
                            return next_elem

                        return None

                    # 1. Full Job Description
                    description = "N/A"
                    desc_elem = get_section_content("Full Job Description")
                    if desc_elem:
                        description = desc_elem.inner_text().strip()
                    else:
                        # Fallback: Search for the container that looks like a description
                        # Next.js/Chakra often puts it in a div with a specific class or ID, but random classes.
                        pass

                    # 2. Qualifications
                    qualifications = []
                    qual_header_text = "Qualifications"
                    if page.locator("h2:has-text('Qualifications')").count() == 0:
                        qual_header_text = "Requirements"
                    
                    qual_elem = get_section_content(qual_header_text)
                    if qual_elem:
                        # Check for list items
                        lis = qual_elem.locator("li").all()
                        if lis:
                             qualifications = [li.inner_text().strip() for li in lis]
                        else:
                            # Check for Spans (Chips)
                            spans = qual_elem.locator("span").all()
                            qualifications = [s.inner_text().strip() for s in spans if len(s.inner_text().strip()) > 1]
                            
                            # If still empty, try splitting text
                            if not qualifications:
                                text = qual_elem.inner_text()
                                qualifications = [l.strip() for l in text.split('\n') if len(l.strip()) > 1]


                    # 3. Job Type (and Details)
                    job_type = "N/A"
                    details_elem = get_section_content("Job Details")
                    if details_elem:
                        text = details_elem.inner_text()
                        types = []
                        if "Full-time" in text: types.append("Full-time")
                        if "Part-time" in text: types.append("Part-time")
                        if "Contract" in text: types.append("Contract")
                        if "Temporary" in text: types.append("Temporary")
                        if "Internship" in text: types.append("Internship")
                        
                        if types:
                            job_type = ", ".join(types)
                        else:
                            lines = text.split('\n')
                            if lines: job_type = lines[0]
                    
                    # --- DEBUG DUMP ---
                    # If we failed to get a description, dump the HTML
                    if description == "N/A" or description == "":
                        print(f"DEBUG: Failed to extract description for '{title}'. Dumping HTML.")
                        # time is already imported globally
                        ts = int(time.time())
                        with open(f"debug_simplyhired_{ts}.html", "w", encoding="utf-8") as f:
                            f.write(page.content())
                        # Also take a screenshot
                        page.screenshot(path=f"debug_simplyhired_{ts}.png")
                        
                        # Try one last ditch effort: Get the WHOLE details pane text
                        # Assuming the pane is the 'aside' or similar
                        try:
                           pane = page.locator("aside").first
                           if pane.count() > 0:
                               all_text = pane.inner_text()
                               description = "FALLBACK EXTRACTION:\n" + all_text[:500] + "..."
                        except:
                            pass

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
