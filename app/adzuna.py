from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import time


BASE_URL_COM = "https://www.adzuna.com/search?q={query}"
BASE_URL_IN = "https://www.adzuna.in/search?q={query}"


def scrape_adzuna_jobs(search_query: str, location: str = None, max_pages: int = 5, freshness: int = None):
    encoded_query = quote_plus(search_query)

    # Smart domain selection: default to .in if location is Indian or user specifies India
    base_url = BASE_URL_COM
    is_india = False
    indian_cities = [
        "bengaluru", "bangalore", "coimbatore", "chennai", "hyderabad", "mumbai", "delhi", "pune", "india",
        "kolkata", "kochi", "ahmedabad", "jaipur", "lucknow", "chandigarh", "surat", "indore", "nagpur",
        "vishakhapatnam", "patna", "vadodara", "ghaziabad", "ludhiana", "agra", "nashik", "faridabad",
        "meerut", "rajkot", "varanasi", "srinagar", "aurangabad", "dhanbad", "amritsar", "navi mumbai",
        "allahabad", "howrah", "gwalior", "jabalpur", "raipur", "jodhpur", "bareilly", "moradabad",
        "mysore", "gurgaon", "noida", "greater noida", "thiruvananthapuram", "bhopal", "visakhapatnam",
        "kanpur", "thane", "solapur", "hubballi", "dharwad", "tiruchirappalli", "bareilly", "aligarh"
    ]
    if location and any(city in location.lower() for city in indian_cities):
        base_url = BASE_URL_IN
        is_india = True

    url = base_url.format(query=encoded_query)
    if location:
        url += f"&w={quote_plus(location)}"
    
    if freshness:
        url += f"&f={freshness}"

    jobs = []
    currency_symbol = "₹" if is_india else "$"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            current_page = 1
            while current_page <= max_pages:
                paginated_url = url if current_page == 1 else f"{url}&p={current_page}"
                print(f"\n🔍 Scraping Adzuna page {current_page}: {paginated_url}")

                page.goto(paginated_url, timeout=60000)
                try:
                    page.wait_for_selector("article[data-aid], .ui-job-card", timeout=10000)
                except:
                    print(f"No job cards found on page {current_page}")
                    break

                # Try extracting embedded JSON for cleaner data
                data = None
                try:
                    data = page.evaluate('() => window["az_wj_data"]')
                except:
                    pass

                page_jobs = []
                if data and "results" in data and len(data["results"]) > 0:
                    results = data["results"]
                    print(f"✅ Found {len(results)} jobs on page {current_page} via JSON")
                    for item in results:
                        try:
                            title = item.get("title", "N/A").replace("<strong>", "").replace("</strong>", "")
                            company = item.get("company", "N/A")
                            job_location = item.get("location_raw", "N/A")
                            
                            salary_min = item.get("salary_min")
                            salary_max = item.get("salary_max")
                            salary = "N/A"
                            if salary_min:
                                salary = f"{currency_symbol}{float(salary_min):,.0f}"
                                if salary_max and salary_max != salary_min:
                                    salary += f" - {currency_symbol}{float(salary_max):,.0f}"

                            description = item.get("description", "N/A")
                            job_id = item.get("id")
                            job_url = f"{base_url.split('/search')[0]}/details/{job_id}" if job_id else "N/A"
                            
                            # Often Adzuna JSON has created or posting_date
                            posted_date = item.get("created", "N/A")

                            page_jobs.append({
                                "keyword": search_query,
                                "title": title,
                                "company": company,
                                "location": job_location,
                                "salary": salary,
                                "job_type": "N/A",
                                "posted_date": posted_date,
                                "qualifications": [],
                                "job_description": description,
                                "job_url": job_url,
                                "source": "Adzuna"
                            })
                        except Exception as e:
                            print(f"❌ Error parsing JSON job: {e}")
                else:
                    # DOM Fallback
                    job_cards = page.locator("article[data-aid], .ui-job-card").all()
                    print(f"⚠️ Falling back to DOM: Found {len(job_cards)} cards")
                    for card in job_cards:
                        try:
                            title_el = card.locator("h2 a[data-js='jobLink'], h2 a").first
                            title = title_el.inner_text().strip() if title_el.count() > 0 else "N/A"
                            job_url = title_el.get_attribute("href") if title_el.count() > 0 else "N/A"
                            if job_url and job_url.startswith("/"):
                                job_url = base_url.split('/search')[0] + job_url

                            company = "N/A"
                            company_el = card.locator(".ui-company, .job-card__company").first
                            if company_el.count() > 0: company = company_el.inner_text().strip()

                            loc = "N/A"
                            location_el = card.locator(".ui-location, .job-card__location").first
                            if location_el.count() > 0: loc = location_el.inner_text().strip()

                            salary = "N/A"
                            salary_el = card.locator(".ui-salary, .job-card__salary").first
                            if salary_el.count() > 0: salary = salary_el.inner_text().strip()

                            posted = "N/A"
                            posted_el = card.locator(".ui-job-card__footer span, .job-card__posted-date").first
                            if posted_el.count() > 0: posted = posted_el.inner_text().strip()

                            desc = "N/A"
                            snippet_el = card.locator(".max-snippet-height, .job-card__description").first
                            if snippet_el.count() > 0: desc = snippet_el.inner_text().strip()

                            page_jobs.append({
                                "keyword": search_query,
                                "title": title,
                                "company": company,
                                "location": loc,
                                "salary": salary,
                                "job_type": "N/A",
                                "posted_date": posted,
                                "qualifications": [],
                                "job_description": desc,
                                "job_url": job_url,
                                "source": "Adzuna"
                            })
                        except Exception as e:
                            print(f"❌ Error parsing DOM card: {e}")

                if not page_jobs:
                    break
                
                jobs.extend(page_jobs)
                current_page += 1
                time.sleep(2)

            # ============================
            # 🔍 JOB DETAIL ENRICHMENT (UNCHANGED)
            # ============================
            print(f"\n🧠 Enriching {len(jobs)} jobs with detail pages...")

            for job in jobs:
                try:
                    url = job.get("job_url")
                    if not url or "adzuna" not in url:
                        continue

                    print(f"➡️ Visiting job detail: {url}")
                    page.goto(url, timeout=30000)
                    page.wait_for_selector("body")

                    # Close email popup if exists
                    try:
                        no_thanks = page.wait_for_selector(
                            "a[data-js='apply-capture-skip']",
                            timeout=3000
                        )
                        if no_thanks:
                            no_thanks.click()
                            page.wait_for_timeout(1000)
                    except:
                        pass

                    # Full description
                    desc_sel = page.query_selector(".adp-body")
                    if desc_sel:
                        full_desc = desc_sel.inner_text().strip()
                        if len(full_desc) > len(job["job_description"]):
                            job["job_description"] = full_desc

                    # JS details enrichment
                    try:
                        js_details = page.evaluate("() => window.job_desc_modal_details")
                        if js_details:
                            job["salary"] = js_details.get("salary", job["salary"])
                            job["company"] = js_details.get("company", job["company"])
                            job["location"] = js_details.get("location", job["location"])
                            if "posted_at" in js_details:
                                job["posted_date"] = js_details["posted_at"]
                    except:
                        pass

                    # Qualifications Extraction
                    quals = []
                    # Try looking for list items in standard sections
                    for sel in page.query_selector_all(".adp-body li, .job-details li"):
                        txt = sel.inner_text().strip()
                        if len(txt) > 3 and len(txt) < 100:
                            quals.append(txt)
                    
                    if quals:
                        job["qualifications"] = quals[:15] # Limit to top 15

                    # Job type extraction
                    types = []

                    ctype = page.query_selector(".ui-contract-type")
                    if ctype:
                        types.append(ctype.inner_text().strip())

                    ctime = page.query_selector(".ui-contract-time")
                    if ctime:
                        types.append(ctime.inner_text().strip())

                    for sel in page.query_selector_all(".ui-pill"):
                        txt = sel.inner_text().strip()
                        if txt:
                            types.append(txt)

                    if types:
                        keywords = ["contract", "permanent", "full time", "part time", "intern"]
                        valid = [t for t in types if any(k in t.lower() for k in keywords)]
                        if valid:
                            job["job_type"] = ", ".join(set(valid))

                    page.wait_for_timeout(1000)

                except Exception as e:
                    print(f"❌ Error enriching job: {e}")

        finally:
            browser.close()

    return jobs