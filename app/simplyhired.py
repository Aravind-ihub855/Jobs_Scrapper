from playwright.sync_api import sync_playwright
import time
from urllib.parse import quote_plus

BASE_URL = "https://www.simplyhired.com/search?q={query}&l="

def scrape_simplyhired_jobs(search_query: str):
    encoded_query = quote_plus(search_query)
    url = BASE_URL.format(query=encoded_query)

    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        try:
            print(f"Navigating to {url}")
            page.goto(url, timeout=60000)

            # Find total number of pages from pagination bar
            total_pages = 1
            try:
                # Wait for pagination bar to load (if present)
                page.wait_for_selector("nav[aria-label='pagination'], ul.pagination", timeout=5000)
                # Try to get the last page number from pagination links
                page_numbers = page.locator("nav[aria-label='pagination'] a, ul.pagination a").all()
                page_nums = []
                for a in page_numbers:
                    try:
                        text = a.inner_text().strip()
                        if text.isdigit():
                            page_nums.append(int(text))
                    except:
                        continue
                if page_nums:
                    total_pages = max(page_nums)
            except Exception as e:
                print(f"Pagination bar not found or error: {e}")

            print(f"Total pages detected: {total_pages}")

            for page_num in range(1, total_pages + 1):
                if page_num == 1:
                    page_url = url
                else:
                    # SimplyHired paginates with /page-{n} at the end
                    page_url = url + f"&pn={page_num}"
                print(f"Scraping page {page_num}: {page_url}")
                page.goto(page_url, timeout=60000)

                # Infinite scroll logic (if needed)
                last_height = page.evaluate("document.body.scrollHeight")
                for _ in range(5):
                    page.mouse.wheel(0, 5000)
                    time.sleep(1)
                    new_height = page.evaluate("document.body.scrollHeight")
                    if new_height == last_height:
                        break
                    last_height = new_height

                job_cards = page.locator("div[data-testid='searchSerpJob']").all()
                if not job_cards:
                    print("No job listings found on the page")

                for card in job_cards:
                    try:
                        card.scroll_into_view_if_needed()
                        title_elem = card.locator("h2[data-testid='searchSerpJobTitle'] > a")
                        if title_elem.count() > 0:
                            title = title_elem.inner_text().strip()
                            href = title_elem.get_attribute("href")
                            job_url = f"https://www.simplyhired.com{href}" if href else None
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
