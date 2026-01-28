from playwright.sync_api import sync_playwright
import time
from urllib.parse import quote_plus

BASE_URL = "https://www.simplyhired.co.in/search?q={query}"

def scrape_simplyhired_jobs(search_query: str, location: str = None, max_pages: int = 5):
    encoded_query = quote_plus(search_query)
    url = BASE_URL.format(query=encoded_query)
    if location:
        url += f"&l={quote_plus(location)}"

    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            print(f"Navigating to {url}")
            page.goto(url, timeout=60000)

            # Find total number of pages from pagination bar
            detected_pages = 1
            try:
                # Wait for pagination bar to load
                page.wait_for_selector("nav[aria-label='pagination'], ul.pagination, .pagination", timeout=8000)
                page_numbers = page.locator("nav[aria-label='pagination'] a, ul.pagination a, .pagination a").all()
                page_nums = []
                for a in page_numbers:
                    try:
                        text = a.inner_text().strip()
                        if text.isdigit():
                            page_nums.append(int(text))
                    except:
                        continue
                if page_nums:
                    detected_pages = max(page_nums)
                    print(f"Max detected pages from bar: {detected_pages}")
            except Exception as e:
                print(f"Pagination bar not found or timeout: {e}")
                # Fallback: Check if there's a "Next" button as a hint there are more pages
                if page.locator("a[aria-label='Next'], a:has-text('Next')").count() > 0:
                    detected_pages = 5 # Assume at least a few pages if "Next" exists
                    print("Next button found, assuming multiple pages.")

            print(f"Pagination detection hinted at {detected_pages} pages, but we will attempt up to {max_pages} pages via 'Next' button clicks.")

            current_page = 1
            while current_page <= max_pages:
                print(f"--- Scraping Page {current_page} ---")
                
                # Wait for job cards
                try:
                    page.wait_for_selector("div[data-testid='searchSerpJob']", timeout=12000)
                except:
                    print(f"Timeout waiting for job cards on page {current_page}")
                
                # Scroll down to ensure all jobs are loaded/visible
                for _ in range(3):
                    page.mouse.wheel(0, 2000)
                    time.sleep(1)

                job_cards = page.locator("div[data-testid='searchSerpJob']").all()
                print(f"Found {len(job_cards)} jobs on page {current_page}")

                if not job_cards:
                    break

                for card in job_cards:
                    try:
                        card.scroll_into_view_if_needed()
                        title_elem = card.locator("h2[data-testid='searchSerpJobTitle'] > a")
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            href = title_elem.get_attribute("href")
                            # Use .co.in for consistency
                            job_url = f"https://www.simplyhired.co.in{href}" if href else None
                        else:
                            title = "N/A"
                            job_url = None

                        company_elem = card.locator("span[data-testid='companyName']")
                        company = company_elem.inner_text().strip() if company_elem.count() > 0 else "N/A"

                        location_elem = card.locator("span[data-testid='searchSerpJobLocation']")
                        location = location_elem.inner_text().strip() if location_elem.count() > 0 else "N/A"

                        salary_elem = card.locator("span[data-testid^='salaryChip']")
                        salary = salary_elem.inner_text().strip() if salary_elem.count() > 0 else "N/A"

                        if title_elem.count() > 0:
                            title_elem.click()
                            time.sleep(2)
                            try:
                                apply_button = page.locator("a:has-text('Quick Apply'), button:has-text('Quick Apply'), a:has-text('Apply Now'), button:has-text('Apply Now')").first
                                if apply_button.count() > 0 and apply_button.is_visible():
                                    box = apply_button.bounding_box()
                                    if box:
                                        page.mouse.move(box["x"], box["y"] + 100)
                                        for _ in range(10):
                                            page.mouse.wheel(0, 500)
                                            time.sleep(0.2)
                                else:
                                    jd_header = page.locator("h2", has_text="Job Details").first
                                    if jd_header.count() > 0:
                                        jd_header.hover()
                                        for _ in range(10):
                                            page.mouse.wheel(0, 500)
                                            time.sleep(0.2)
                            except Exception as e:
                                print(f"Scrolling error: {e}")
                            time.sleep(1)

                        posted_date = "N/A"
                        try:
                            # From user screenshot: viewJobBodyJobPostingTimestamp -> detailText
                            posted_elem = page.locator("span[data-testid='viewJobBodyJobPostingTimestamp'] span[data-testid='detailText']").first
                            if posted_elem.count() > 0:
                                posted_date = posted_elem.inner_text().strip()
                        except:
                            pass

                        def safe_get_text(locator):
                            try:
                                if locator.count() > 0:
                                    return locator.inner_text().strip()
                            except:
                                pass
                            return "N/A"

                        def get_section_content(header_text):
                            header = page.locator(f"h2:has-text('{header_text}'), h3:has-text('{header_text}'), h4:has-text('{header_text}')").first
                            if header.count() == 0:
                                header = page.locator(f"div:has-text('{header_text}'), span:has-text('{header_text}'), strong:has-text('{header_text}')").filter(has_text=header_text).last
                            if header.count() == 0:
                                return None
                            sibling = header.locator("xpath=following-sibling::div").first
                            if sibling.count() > 0 and len(sibling.inner_text().strip()) > 0:
                                return sibling
                            parent_sibling = header.locator("xpath=../following-sibling::div").first
                            if parent_sibling.count() > 0 and len(parent_sibling.inner_text().strip()) > 0:
                                return parent_sibling
                            next_elem = header.locator("xpath=following-sibling::*[1]").first
                            if next_elem.count() > 0:
                                return next_elem
                            return None

                        description = "N/A"
                        desc_elem = get_section_content("Full Job Description")
                        if desc_elem:
                            description = desc_elem.inner_text().strip()

                        qualifications = []
                        # Try the specific data-testid from user screenshot first
                        try:
                            qual_items = page.locator("span[data-testid='viewJobQualificationItem']").all()
                            if qual_items:
                                qualifications = [q.inner_text().strip() for q in qual_items if q.inner_text().strip()]
                        except:
                            pass
                        
                        if not qualifications:
                            qual_header_text = "Qualifications"
                            if page.locator("h2:has-text('Qualifications')").count() == 0:
                                qual_header_text = "Requirements"
                            qual_elem = get_section_content(qual_header_text)
                            if qual_elem:
                                lis = qual_elem.locator("li").all()
                                if lis:
                                    qualifications = [li.inner_text().strip() for li in lis]
                                else:
                                    spans = qual_elem.locator("span").all()
                                    qualifications = [s.inner_text().strip() for s in spans if len(s.inner_text().strip()) > 1]
                                    if not qualifications:
                                        text = qual_elem.inner_text()
                                        qualifications = [l.strip() for l in text.split('\n') if len(l.strip()) > 1]

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

                        if description == "N/A" or description == "":
                            print(f"DEBUG: Failed to extract description for '{title}'. Dumping HTML.")
                            ts = int(time.time())
                            with open(f"debug_simplyhired_{ts}.html", "w", encoding="utf-8") as f:
                                f.write(page.content())
                            page.screenshot(path=f"debug_simplyhired_{ts}.png")
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
                            "posted_date": posted_date,
                            "qualifications": qualifications,
                            "job_description": description,
                            "job_url": job_url,
                            "source": "SimplyHired"
                        }
                        jobs.append(job)
                    except Exception as e:
                        print(f"Error processing individual job: {e}")
                        continue
                
                # Check for Next Page
                if current_page >= max_pages:
                    break
                    
                next_button = page.locator("a[aria-label='Next'], a:has-text('Next')").first
                if next_button.count() > 0:
                    print(f"Moving from page {current_page} to {current_page + 1}")
                    try:
                        next_button.scroll_into_view_if_needed()
                        next_button.click()
                        current_page += 1
                        time.sleep(5) # Wait for next page to load results
                    except Exception as e:
                        print(f"Could not click next button: {e}")
                        break
                else:
                    print(f"No more pages found after page {current_page}")
                    break
        except Exception as e:
            print(f"Scraping error: {e}")
        finally:
            # Safely close page and browser to avoid crash if already closed
            try:
                if not page.is_closed():
                    page.close()
            except Exception as e:
                print(f"Error closing page: {e}")
            try:
                browser.close()
            except Exception as e:
                print(f"Error closing browser: {e}")
    return jobs