from playwright.sync_api import sync_playwright
from urllib.parse import quote_plus
from app.database import adzuna_collection

BASE_URL = "https://www.adzuna.com/search?q={query}"

def scrape_adzuna_jobs(search_query: str, location: str = None):
    encoded_query = quote_plus(search_query)
    url = BASE_URL.format(query=encoded_query)
    if location:
        url += f"&w={quote_plus(location)}"

    jobs = []

    with sync_playwright() as p:
        # Launch browser (Headless can be True here as we are just reading a JS variable)
        browser = p.chromium.launch(headless=True) 
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
            data = page.evaluate('() => window["az_wj_data"]')
            
            if data and "results" in data:
                results = data["results"]
                print(f"Found {len(results)} jobs in embedded data.")

                for item in results:
                    # Extract fields from the JSON object
                    title = item.get("title", "N/A").replace("<strong>", "").replace("</strong>", "") # Clean formatting
                    company = item.get("company", "N/A")
                    
                    # Location seems to be in 'location_raw' or 'location' object
                    job_location = item.get("location_raw", "N/A")
                    
                    # Salary
                    salary_min = item.get("salary_min")
                    salary_max = item.get("salary_max")
                    salary = "N/A"
                    if salary_min:
                        salary = f"${salary_min:,.0f}"
                        if salary_max and salary_max != salary_min:
                            salary += f" - ${salary_max:,.0f}"
                    
                    # Description is directly available!
                    description = item.get("description", "N/A")
                    
                    # Job URL (usually constructed or in 'redirect_url' / 'canonical_url' - checking user source)
                    # The source has "id": "5435615366" and uses links like "https://www.adzuna.com/details/5435615366"
                    job_id = item.get("id")
                    job_url = f"https://www.adzuna.com/details/{job_id}" if job_id else "N/A"
                    
                    # Adzuna JSON doesn't strictly split qualifications vs description
                    # We will leave qualifications as empty list or try to parse if needed, 
                    # but usually description covers it.
                    qualifications = []
                    
                    # Job type might be in 'category' or 'contract_type' (not always present)
                    # We can scan description or tags if needed.
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
            else:
                print("No 'az_wj_data' found or no results.")

        except Exception as e:
            print(f"Error scraping Adzuna: {e}")
        finally:
            browser.close()

    return jobs
