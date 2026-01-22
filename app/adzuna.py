from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
import time


BASE_URL_COM = "https://www.adzuna.com/search?q={query}"
BASE_URL_IN = "https://www.adzuna.in/search?q={query}"


def scrape_adzuna_jobs(search_query: str, location: str = None):
    encoded_query = quote_plus(search_query)

    # Domain selection
    base_url = BASE_URL_COM
    if location and location.lower() == "india":
        base_url = BASE_URL_IN

    url = base_url.format(query=encoded_query)

    if location:
        url += f"&w={quote_plus(location)}"

    jobs = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        try:
            page_number = 1

            # ============================
            # 🔁 PAGINATION LOOP (NEW)
            # ============================
            while True:
                paginated_url = url if page_number == 1 else f"{url}&p={page_number}"
                print(f"\n🔍 Scraping Adzuna page {page_number}: {paginated_url}")

                page.goto(paginated_url, timeout=60000)
                page.wait_for_selector("body")

                # Try extracting embedded JSON
                data = None
                try:
                    data = page.evaluate('() => window["az_wj_data"]')
                except:
                    pass

                # ============================
                # ✅ JSON EXTRACTION PATH
                # ============================
                if data and "results" in data and len(data["results"]) > 0:
                    results = data["results"]
                    print(f"✅ Found {len(results)} jobs on page {page_number}")

                    for item in results:
                        try:
                            title = item.get("title", "N/A") \
                                .replace("<strong>", "") \
                                .replace("</strong>", "")

                            company = item.get("company", "N/A")
                            job_location = item.get("location_raw", "N/A")

                            salary_min = item.get("salary_min")
                            salary_max = item.get("salary_max")
                            salary = "N/A"

                            try:
                                if salary_min:
                                    salary = f"${float(salary_min):,.0f}"
                                    if salary_max and salary_max != salary_min:
                                        salary += f" - ${float(salary_max):,.0f}"
                            except:
                                salary = str(salary_min) if salary_min else "N/A"

                            description = item.get("description", "N/A")

                            job_id = item.get("id")
                            job_url = (
                                f"https://www.adzuna.com/details/{job_id}"
                                if job_id else "N/A"
                            )

                            jobs.append({
                                "keyword": search_query,
                                "title": title,
                                "company": company,
                                "location": job_location,
                                "salary": salary,
                                "job_type": "N/A",
                                "qualifications": [],
                                "job_description": description,
                                "job_url": job_url,
                                "source": "Adzuna"
                            })

                        except Exception as e:
                            print(f"❌ Error parsing JSON job: {e}")

                # ============================
                # 🔁 DOM FALLBACK (UNCHANGED)
                # ============================
                else:
                    print("⚠️ No az_wj_data found. Falling back to DOM scraping.")

                    try:
                        page.wait_for_selector("article[data-aid]", timeout=10000)
                        job_cards = page.query_selector_all("article[data-aid]")

                        if not job_cards:
                            print("⛔ No DOM jobs found. Ending pagination.")
                            break

                        for card in job_cards:
                            try:
                                title_el = card.query_selector("h2 a[data-js='jobLink']")
                                title = title_el.inner_text().strip() if title_el else "N/A"
                                job_url = title_el.get_attribute("href") if title_el else "N/A"

                                company_el = card.query_selector(".ui-company")
                                company = company_el.inner_text().strip() if company_el else "N/A"

                                location_el = card.query_selector(".ui-location")
                                job_location = location_el.inner_text().strip() if location_el else "N/A"

                                snippet_el = card.query_selector(".max-snippet-height")
                                description = snippet_el.inner_text().strip() if snippet_el else "N/A"

                                jobs.append({
                                    "keyword": search_query,
                                    "title": title,
                                    "company": company,
                                    "location": job_location,
                                    "salary": "N/A",
                                    "job_type": "N/A",
                                    "qualifications": [],
                                    "job_description": description,
                                    "job_url": job_url,
                                    "source": "Adzuna"
                                })

                            except Exception as e:
                                print(f"❌ Error parsing DOM card: {e}")

                    except Exception as e:
                        print(f"❌ DOM fallback failed: {e}")
                        break

                page_number += 1
                page.wait_for_timeout(1500)

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
                    except:
                        pass

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
