from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
from app.database import adzuna_collection

BASE_URL = "https://www.adzuna.com/search?q={query}"

def scrape_adzuna_jobs(search_query: str, location: str = None):
    encoded_query = quote_plus(search_query)
    base_url = "https://www.adzuna.com/search?q={query}"
    
    # Handle country-specific domains
    if location and location.lower() == "india":
        base_url = "https://www.adzuna.in/search?q={query}"
        
    url = base_url.format(query=encoded_query)
    
    if location:
        url += f"&w={quote_plus(location)}"

    jobs = []

    with sync_playwright() as p:
        # Launch browser (Headless can be True here as we are just reading a JS variable)
        browser = p.chromium.launch(headless=False) 
        page = browser.new_page()
        
        try:
            print(f"Navigating to {url}")
            page.goto(url, timeout=60000)
            
            # Wait for the variable to be populated - usually immediate as it's in the initial HTML
            # but a small sleep or waiting for selector helps ensure page load
            try:
                page.wait_for_selector("script", state="attached", timeout=10000)
            except:
                pass

            # Extract the data directly from the window object
            # az_wj_data contains the search results under 'results' key
            data = None
            try:
                data = page.evaluate('() => window["az_wj_data"]')
            except:
                pass
            
            if data and "results" in data and len(data["results"]) > 0:
                results = data["results"]
                print(f"Found {len(results)} jobs in embedded data.")

                for item in results:
                    try:
                        # Extract fields from the JSON object
                        title = item.get("title", "N/A").replace("<strong>", "").replace("</strong>", "") # Clean formatting
                        company = item.get("company", "N/A")
                        
                        # Location seems to be in 'location_raw' or 'location' object
                        job_location = item.get("location_raw", "N/A")
                        
                        # Salary
                        salary_min = item.get("salary_min")
                        salary_max = item.get("salary_max")
                        salary = "N/A"
                        try:
                            if salary_min:
                                salary = f"${float(salary_min):,.0f}"
                                if salary_max and salary_max != salary_min:
                                    salary += f" - ${float(salary_max):,.0f}"
                        except Exception as e:
                            print(f"Salary formatting error: {e}")
                            salary = str(salary_min) if salary_min else "N/A"
                        
                        # Description is directly available!
                        description = item.get("description", "N/A")
                        
                        # Job URL (usually constructed or in 'redirect_url' / 'canonical_url' - checking user source)
                        # The source has "id": "5435615366" and uses links like "https://www.adzuna.com/details/5435615366"
                        job_id = item.get("id")
                        job_url = f"https://www.adzuna.com/details/{job_id}" if job_id else "N/A"
                        
                        qualifications = []
                        job_type = "N/A" # Default

                        job = {
                            "keyword": search_query,
                            "title": title,
                            "company": company,
                            "location": job_location,
                            "salary": salary,
                            "job_type": job_type,
                            "qualifications": qualifications,
                            "job_description": description,
                            "job_url": job_url,
                            "source": "Adzuna"
                        }
                        jobs.append(job)
                    except Exception as e:
                         print(f"Error parsing JSON item: {e}")
            else:
                print("No 'az_wj_data' found or no results. Falling back to DOM scraping.")
                # Fallback: Scrape DOM directly
                # Wait for job cards
                try:
                    page.wait_for_selector("article[data-aid]", timeout=10000)
                    job_cards = page.query_selector_all("article[data-aid]")
                    
                    for card in job_cards:
                        try:
                            title_el = card.query_selector("h2 a[data-js='jobLink']")
                            title = title_el.inner_text().strip() if title_el else "N/A"
                            job_url = title_el.get_attribute("href") if title_el else "N/A"
                            if job_url != "N/A" and not job_url.startswith("http"):
                                 # Adzuna urls might be relative? Source showed absolute but let's be safe
                                 pass 

                            company_el = card.query_selector(".ui-company")
                            company = company_el.inner_text().strip() if company_el else "N/A"

                            location_el = card.query_selector(".ui-location")
                            job_location = location_el.inner_text().strip() if location_el else "N/A"

                            snippet_el = card.query_selector(".max-snippet-height")
                            description = snippet_el.inner_text().strip() if snippet_el else "N/A"
                            
                            # Try to extract salary from snippet or extra tags if available, 
                            # or just leave N/A for inconsistent DOM structure
                            salary = "N/A"

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
                            print(f"Error parsing card: {e}")
                except Exception as e:
                     print(f"Fallback scraping failed: {e}")
                     # Debug dump
                     import time
                     ts = int(time.time())
                     page.screenshot(path=f"debug_adzuna_fallback_{ts}.png")
                     with open(f"debug_adzuna_fallback_{ts}.html", "w", encoding="utf-8") as f:
                         f.write(page.content())

            if jobs:
                print(f"Scraping details for {len(jobs)} jobs...")
                for job in jobs:
                    try:
                        url = job["job_url"]
                        if url and "adzuna" in url and url != "N/A":
                            print(f"Scraping details: {url}")
                            page.goto(url, timeout=30000)
                            
                            # Wait for content
                            # Wait for content
                            page.wait_for_selector("body")

                            # Handle "Email Alert" popup (Apply Capture)
                            try:
                                 # Look for the "No thanks" link with a short timeout
                                 no_thanks = page.wait_for_selector("a[data-js='apply-capture-skip']", state="visible", timeout=3000)
                                 if no_thanks:
                                     print("Closing email alert popup...")
                                     no_thanks.click()
                                     # Wait for it to disappear/animate
                                     page.wait_for_timeout(1000)
                            except:
                                 # It's fine if the popup doesn't appear
                                 pass
                            
                            # Extract logic
                            # 1. Full Description
                            # Per source, it's in <section class="adp-body ...">
                            description_sel = page.query_selector(".adp-body")
                            if description_sel:
                                full_desc = description_sel.inner_text().strip()
                                if len(full_desc) > len(job["job_description"]):
                                    job["job_description"] = full_desc
                            
                            # 2. Extract Data from JS Variable (Cleanest source for Salary/Location/Company)
                            # window.job_desc_modal_details = { title, salary, location, company }
                            try:
                                js_details = page.evaluate("() => window.job_desc_modal_details")
                                if js_details:
                                    if "salary" in js_details and js_details["salary"]:
                                         job["salary"] = js_details["salary"]
                                    if "company" in js_details and js_details["company"]:
                                         job["company"] = js_details["company"]
                                    if "location" in js_details and js_details["location"]:
                                         job["location"] = js_details["location"]
                            except Exception as e:
                                print(f"JS extraction error: {e}")

                            # 3. Contract Type / Hours / Job Type
                            # Per source: .ui-contract-type, .ui-contract-time
                            types = []
                            
                            ctype = page.query_selector(".ui-contract-type")
                            if ctype:
                                types.append(ctype.inner_text().strip())
                            
                            ctime = page.query_selector(".ui-contract-time")
                            if ctime:
                                types.append(ctime.inner_text().strip())
                                
                            # Fallback to stats table if needed
                            stats_sels = page.query_selector_all("table[class*='stats'] tr, .ui-pill")
                            for sel in stats_sels:
                                txt = sel.inner_text().strip()
                                if txt and txt not in types:
                                    types.append(txt)

                            if types:
                                 # Filter common keywords
                                 keywords = ["Contract", "Permanent", "Full time", "Part time", "Internship"]
                                 valid_types = [t for t in types if any(k.lower() in t.lower() for k in keywords)]
                                 if valid_types:
                                     job["job_type"] = ", ".join(valid_types)
                            
                            # Small sleep to be polite
                            page.wait_for_timeout(1000)
    
                    except Exception as e:
                        print(f"Error scraping details for {job.get('title')}: {e}")

        except Exception as e:
            print(f"Error scraping Adzuna: {e}")
        finally:
            browser.close()

    return jobs
