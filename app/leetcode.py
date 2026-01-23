from playwright.sync_api import sync_playwright
import time
import json

def scrape_leetcode_questions(problem_list_slug: str):
    """
    Scrapes LeetCode questions from a problem list slug (e.g., 'iterator').
    """
    base_url = f"https://leetcode.com/problem-list/{problem_list_slug}/"
    questions = []

    with sync_playwright() as p:
        # Launch browser
        browser = p.chromium.launch(headless=True)
        # Using a realistic user agent
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        try:
            print(f"🔍 Navigating to problem list: {base_url}")
            page.goto(base_url, wait_until="networkidle", timeout=60000)
            
            # Wait for the problem list content to load (v2 UI uses a different structure)
            # We look for links that start with /problems/
            page.wait_for_selector('a[href*="/problems/"]', timeout=30000)
            
            # Additional wait for full hydration
            time.sleep(3)
            
            # Extract links and basic info from the list
            # The v2 UI often has each problem as a direct <a> tag or wrapped in one
            links = page.query_selector_all('a[href*="/problems/"]')
            print(f"✅ Found {len(links)} potential links")

            question_links = []
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if not href or "/problems/" not in href:
                        continue
                        
                    # Filter out non-problem links (like discussions or solutions if they match)
                    # Problem links usually look like /problems/problem-name/
                    if href.count('/') < 2:
                        continue

                    # Get title - usually the first div with text or a class like truncate
                    title_el = link.query_selector('div.truncate')
                    if not title_el:
                        # Fallback: get all text and take the first line or use innerText
                        title = link.inner_text().split('\n')[0].strip()
                    else:
                        title = title_el.inner_text().strip()

                    # Get difficulty - usually a <p> tag
                    difficulty = "N/A"
                    diff_el = link.query_selector('p')
                    if diff_el:
                        difficulty = diff_el.inner_text().strip()

                    full_url = f"https://leetcode.com{href}" if href.startswith('/') else href
                    
                    # Avoid duplicates
                    if not any(q['url'] == full_url for q in question_links):
                        question_links.append({
                            "title": title,
                            "url": full_url,
                            "difficulty": difficulty
                        })
                except Exception as e:
                    print(f"⚠️ Error parsing list item: {e}")

            print(f"🚀 Found {len(question_links)} unique questions. Starting detailed scrape...")

            # Visit each question page to get details
            for q in question_links:
                try:
                    print(f"➡️ Scraping details for: {q['title']}")
                    page.goto(q['url'], wait_until="networkidle", timeout=30000)
                    
                    # Wait for description content container
                    # selector: div[data-track-load="description_content"]
                    page.wait_for_selector('div[data-track-load="description_content"]', timeout=20000)
                    
                    # Extract the whole description
                    desc_el = page.query_selector('div[data-track-load="description_content"]')
                    if not desc_el:
                        print(f"⚠️ Could not find description for {q['title']}")
                        continue

                    # Get inner text for simple display
                    description_text = desc_el.inner_text().strip()
                    
                    # More structured extraction
                    # Examples are usually in <pre> tags
                    examples = []
                    pre_tags = desc_el.query_selector_all('pre')
                    for pre in pre_tags:
                        examples.append(pre.inner_text().strip())
                    
                    # Constraints are usually in a <ul> tag, often the last one or after a specific header
                    constraints = []
                    ul_tags = desc_el.query_selector_all('ul')
                    if ul_tags:
                        # Try to find the one that looks like constraints (usually short items)
                        # Or just take the last one as a heuristic
                        constraints.append(ul_tags[-1].inner_text().strip())

                    questions.append({
                        "title": q["title"],
                        "url": q["url"],
                        "difficulty": q["difficulty"],
                        "description": description_text,
                        "examples": examples,
                        "constraints": constraints,
                        "source": "LeetCode",
                        "slug": problem_list_slug
                    })
                    
                    # Delay to avoid rate limiting
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Error scraping {q['title']}: {e}")

        except Exception as e:
            print(f"❌ Error navigating to list: {e}")
        finally:
            browser.close()

    return questions
