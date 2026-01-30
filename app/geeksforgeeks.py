from playwright.sync_api import sync_playwright
import re
import time
from app.database import gfg_collection
import asyncio

def clean_text(text: str) -> str:
    """Removes emojis, icons, and extra whitespace from text."""
    if not text:
        return ""
    # Remove non-ASCII characters (emojis/icons usually fall here)
    text = text.encode('ascii', 'ignore').decode('ascii')
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def slugify(text: str) -> str:
    """Converts a title into a GFG-style problem slug."""
    # Convert to lowercase
    text = text.lower()
    # Remove special characters
    text = re.sub(r'[^a-z0-9\s-]', '', text)
    # Replace spaces with hyphens
    text = re.sub(r'\s+', '-', text)
    # Remove multiple hyphens
    text = re.sub(r'-+', '-', text)
    return text.strip('-')

def parse_problem_content(raw_text: str) -> dict:
    """
    Parses raw problem description text into granular structured fields.
    """
    if not raw_text:
        return {
            "description": "", "examples": [], "constraints": "",
            "your_task": "", "expected_time_complexity": "", "expected_aux_space": ""
        }

    sections = {
        "description": "",
        "examples": [],
        "your_task": "",
        "expected_time_complexity": "",
        "expected_aux_space": "",
        "constraints": ""
    }

    # Extract Constraints
    constraints_match = re.search(r'Constraints:\s*(.*)', raw_text, re.DOTALL | re.IGNORECASE)
    if constraints_match:
        sections["constraints"] = constraints_match.group(1).strip()
        raw_text = raw_text[:constraints_match.start()].strip()

    # Extract Expected Complexities
    time_match = re.search(r'Expected Time Complexity:\s*(.*?)(?=Expected Auxiliary Space:|$)', raw_text, re.DOTALL | re.IGNORECASE)
    if time_match:
        sections["expected_time_complexity"] = time_match.group(1).strip()
        
    aux_match = re.search(r'Expected Auxiliary Space:\s*(.*?)(?=Constraints:|$|Your Task:)', raw_text, re.DOTALL | re.IGNORECASE)
    if aux_match:
        sections["expected_aux_space"] = aux_match.group(1).strip()
        
    # Clean up raw_text from complexities if found (they are often at the bottom before constraints)
    raw_text = re.sub(r'Expected Time Complexity:.*', '', raw_text, flags=re.DOTALL | re.IGNORECASE).strip()
    raw_text = re.sub(r'Expected Auxiliary Space:.*', '', raw_text, flags=re.DOTALL | re.IGNORECASE).strip()

    # Extract Your Task
    task_match = re.search(r'Your Task:\s*(.*?)(?=Expected|$|Constraints:)', raw_text, re.DOTALL | re.IGNORECASE)
    if task_match:
        sections["your_task"] = task_match.group(1).strip()
        raw_text = raw_text[:task_match.start()].strip()

    # Split Examples more robustly
    # Look for "Example X:", "Example:", "Examples:", or just "Input:" headers
    example_split_pattern = r'(Example \d+:|Example:|Examples:|Input:)'
    parts = re.split(example_split_pattern, raw_text, flags=re.IGNORECASE)
    
    # parts[0] is the core description
    sections["description"] = parts[0].strip()
    
    # Subsequent parts are pairs of (Header, Content)
    current_example_content = ""
    for i in range(1, len(parts), 2):
        header = parts[i]
        content = parts[i+1] if i+1 < len(parts) else ""
        
        # If header is "Input:", we prepend it to content to keep the standard parsing
        if header.lower().startswith("input"):
            full_block = "Input: " + content
        else:
            full_block = content
            
        # Parse individual examples from the block
        # Blocks can contain multiple Input/Output pairs if the split was on "Examples:"
        sub_blocks = re.split(r'(Input:)', full_block, flags=re.IGNORECASE)
        for j in range(1, len(sub_blocks), 2):
            sub_content = sub_blocks[j+1] if j+1 < len(sub_blocks) else ""
            example = {"input": "", "output": "", "explanation": ""}
            
            input_match = re.search(r'(.*?)(?=Output:|$)', sub_content, re.DOTALL | re.IGNORECASE)
            if input_match:
                example["input"] = input_match.group(1).strip()
            
            output_match = re.search(r'Output:\s*(.*?)(?=Explanation:|$)', sub_content, re.DOTALL | re.IGNORECASE)
            if output_match:
                example["output"] = output_match.group(1).strip()
                
            explanation_match = re.search(r'Explanation:\s*(.*)', sub_content, re.DOTALL | re.IGNORECASE)
            if explanation_match:
                # Limit explanation until next header if any (though usually at end of block)
                example["explanation"] = explanation_match.group(1).strip()
                
            if example["input"] or example["output"]:
                sections["examples"].append(example)

    return sections

def scrape_gfg_questions(search_query: str, pages: int = 1, company: str = None):
    """
    Scrapes GeeksforGeeks questions using the internal Practice API for list data
    and Playwright for detail extraction.
    """
    scraped_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        for i in range(1, pages + 1):
            # Use the practice API instead of HTML scraping
            # This is much more reliable as it gives us the exact slugs
            api_url = f"https://practiceapi.geeksforgeeks.org/api/vr/problems/?pageMode=explore&page={i}&sortBy=submissions"
            
            if search_query:
                api_url += f"&category={search_query}"
            
            if company:
                api_url += f"&company={company}"
            
            print(f"[GFG List] Fetching GFG list from API: {api_url}")
            
            try:
                # We use page.goto and then evaluate to fetch the JSON via the browser's network context
                # to avoid CORS/Auth issues that might arise with direct requests
                page.goto(api_url, wait_until="networkidle", timeout=60000)
                
                # extract JSON from the page content (Playwright usually renders it or we can fetch it)
                page_content = page.evaluate("() => document.body.innerText")
                print(f"[GFG List] Page content preview: {page_content[:500]}")
                
                try:
                    json_data = page.evaluate("() => JSON.parse(document.body.innerText)")
                except Exception as je:
                    print(f"[GFG List] JSON parse error: {je}")
                    # Try to find JSON in the page more robustly if document.body.innerText isn't raw JSON
                    json_text = page.evaluate("""() => {
                        const pre = document.querySelector('pre');
                        return pre ? pre.innerText : document.body.innerText;
                    }""")
                    import json
                    json_data = json.loads(json_text)

                problems = json_data.get("results", [])
                print(f"[GFG List] Received {len(problems)} problems from API on page {i}")
                
                if not problems and not company:
                    # Fallback to search if category returns nothing (skip if company is set as it's a specific filter)
                    api_url = f"https://practiceapi.geeksforgeeks.org/api/vr/problems/?pageMode=explore&page={i}&search={search_query}&sortBy=submissions"
                    page.goto(api_url, wait_until="networkidle", timeout=60000)
                    json_data = page.evaluate("() => JSON.parse(document.body.innerText)")
                    problems = json_data.get("results", [])
                    print(f"[GFG List] Received {len(problems)} problems from Search API on page {i}")

                for prob in problems:
                    slug = prob.get("slug")
                    if not slug:
                        continue
                        
                    title = prob.get("problem_name", "")
                    # Construct reliable URL
                    problem_url = f"https://www.geeksforgeeks.org/problems/{slug}/1"
                    scraped_data.append({
                        "title": clean_text(title),
                        "url": problem_url,
                        "difficulty": clean_text(prob.get("difficulty", "")),
                        "submissions": clean_text(str(prob.get("total_submissions", ""))),
                        "accuracy": clean_text(str(prob.get("accuracy", ""))),
                        "platform": "GeeksforGeeks",
                        "search_query": search_query,
                        "company": company
                    })
            except Exception as e:
                print(f"[GFG List] Error fetching GFG list page {i}: {e}")
                break

        print(f"[GFG List] Found {len(scraped_data)} unique problems. Starting details...")

        # Detail Scraping
        for item in scraped_data:
            try:
                print(f"[GFG Detail] Scraping details for: {item['title']}")
                detail_page = context.new_page()
                
                detail_page.goto(item["url"], wait_until="domcontentloaded", timeout=60000)
                
                # Check for "Oops" error or empty page
                try:
                    # Longer wait for the dynamic content container
                    detail_page.wait_for_selector('div[class*="problems_problem_content"]', timeout=20000)
                except:
                    print(f"[GFG Detail] Content container not found for {item['title']}. Retrying...")
                    # Sometimes a reload helps if it's a transient GFG error
                    detail_page.reload(wait_until="domcontentloaded")
                    try:
                        detail_page.wait_for_selector('div[class*="problems_problem_content"]', timeout=15000)
                    except:
                        print(f"[GFG Detail] Failed to find content for {item['title']} after retry.")
                        detail_page.close()
                        continue
                
                # Scroll to trigger any lazy loads
                detail_page.evaluate("window.scrollBy(0, 400)")
                time.sleep(1)
                
                content_el = detail_page.query_selector('div[class*="problems_problem_content"]')
                
                # Extract content with superscript handling for constraints
                detail_data = detail_page.evaluate("""
                    () => {
                        const contentDiv = document.querySelector('div[class*="problems_problem_content"]');
                        if (!contentDiv) return { description_text: "", constraints_html: "" };
                        
                        // Helper function to convert superscript to caret notation
                        const convertSupToCaretNotation = (element) => {
                            const clone = element.cloneNode(true);
                            const sups = clone.querySelectorAll('sup');
                            sups.forEach(sup => {
                                const text = sup.textContent;
                                sup.replaceWith(`^${text}`);
                            });
                            return clone.innerText.trim();
                        };
                        
                        return {
                            description_text: convertSupToCaretNotation(contentDiv),
                            constraints_html: contentDiv.innerHTML
                        };
                    }
                """)
                
                description_text = detail_data.get("description_text", "") if detail_data else ""
                
                # Parse structured content
                structured_content = parse_problem_content(description_text)
                
                extra = detail_page.evaluate("""
                    () => {
                        const result = { complexity: "" };
                        const strongs = Array.from(document.querySelectorAll('strong'));
                        const ch = strongs.find(s => s.innerText.includes('Expected'));
                        if (ch) result.complexity = ch.parentElement.innerText.trim();
                        return result;
                    }
                """)
                
                item.update({
                    "description": structured_content["description"],
                    "examples": structured_content["examples"],
                    "constraints": structured_content["constraints"],
                    "your_task": structured_content["your_task"],
                    "expected_time_complexity": structured_content["expected_time_complexity"] or clean_text(extra["complexity"]),
                    "expected_aux_space": structured_content["expected_aux_space"]
                })
                
                detail_page.close()
                time.sleep(1) # Gentle delay between problems
            except Exception as e:
                print(f"[GFG Detail] Error detail scrape for {item['title']}: {e}")
                try:
                    detail_page.close()
                except:
                    pass

        browser.close()
    
    return scraped_data
