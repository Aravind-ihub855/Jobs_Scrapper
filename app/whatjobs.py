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

    base_url = "https://en-in.whatjobs.com/jobs"
    query_slug = slugify(query)
    search_url = f"{base_url}/{query_slug}"

    print(f"Scraping WhatJobs URL: {search_url}")

    with sync_playwright() as p:
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

            # --- Find total number of pages from pagination bar ---
            total_pages = 1
            try:
                # Find all pagination number links
                pagination_links = page.query_selector_all(".pagination li.page-item.searchResultPage:not(.active) span.page-link, .pagination li.page-item.searchResultPage:not(.active) a.page-link")
                page_numbers = []
                for link in pagination_links:
                    try:
                        text = link.inner_text().strip()
                        if text.isdigit():
                            page_numbers.append(int(text))
                    except Exception:
                        continue
                if page_numbers:
                    total_pages = max(page_numbers)
            except Exception as e:
                print(f"Could not determine total pages: {e}")

            print(f"Total pages detected: {total_pages}")

            # --- Loop through all pages ---
            for current_page in range(1, total_pages + 1):
                if current_page == 1:
                    page_url = search_url
                else:
                    page_url = f"{search_url}/page-{current_page}"

                print(f"\n=== Scraping Page {current_page} ({page_url}) ===")
                if current_page > 1:
                    page.goto(page_url, timeout=60000)
                    page.wait_for_selector(".ajCard", timeout=15000)

                cards = page.query_selector_all(".ajCard")
                print(f"Found {len(cards)} cards on page {current_page}.")

                for i, card in enumerate(cards):
                    try:
                        card.scroll_into_view_if_needed()

                        # 1. Title
                        title_el = card.query_selector(".jobTitle")
                        title = title_el.inner_text().strip() if title_el else "N/A"

                        # 2. Company & Location
                        company = "N/A"
                        company_icon = card.query_selector(".companyName")
                        if company_icon:
                            company = company_icon.evaluate("el => el.parentElement.innerText").strip()

                        location_text = "N/A"
                        loc_icon = card.query_selector(".location")
                        if loc_icon:
                            location_text = loc_icon.evaluate("el => el.parentElement.innerText").strip()

                        # 3. Salary
                        salary = "N/A"
                        salary_el = card.query_selector(".aiSalary")
                        if salary_el:
                            salary = salary_el.inner_text().strip()

                        # 4. Description
                        description = "N/A"
                        desc_el = card.query_selector(".ajCardDetails") or card.query_selector(".jDesc")
                        if desc_el:
                            raw_desc = desc_el.text_content().strip()
                            if len(raw_desc) > 100:
                                description = raw_desc
                                description = description.replace("Tap Again To Close", "").strip()
                                description = description.replace("Job Description", "").strip()

                        if description == "N/A" or len(description) < 100:
                            is_expanded = card.get_attribute("data-expanded")
                            if is_expanded != "true":
                                time.sleep(0.5)
                                try:
                                    card.click(timeout=3000)
                                    page.wait_for_timeout(1000)
                                    if desc_el:
                                        description = desc_el.inner_text().strip()
                                except Exception as click_err:
                                    print(f"Click failed for card {i}, skipping expansion: {click_err}")

                        job_id = card.get_attribute("data-id") or f"whatjobs-{i}"
                        job_link = f"{search_url}?id={job_id}"

                        job_data = {
                            "title": title,
                            "company": company,
                            "location": location_text,
                            "job_description": description[:500] + "..." if len(description) > 500 else description,
                            "job_url": job_link,
                            "salary": salary,
                            "job_board": "whatjobs",
                            "post_date": "N/A"
                        }
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