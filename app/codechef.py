from playwright.sync_api import sync_playwright
import re
import time

def clean_text(text: str) -> str:
    """Removes extra whitespace from text."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def scrape_codechef_questions(tag: str, pages: int = 1):
    """
    Scrapes CodeChef questions for a specific tag using Playwright.
    """
    scraped_data = []
    base_url = "https://www.codechef.com"
    list_url = f"{base_url}/practice-old/tags/{tag}"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        print(f"[CodeChef List] Navigating to: {list_url}")
        try:
            page.goto(list_url, wait_until="networkidle", timeout=60000)
            
            # Wait for the table to load
            page.wait_for_selector('table.MuiTable-root', timeout=20000)
            
            # Extract problems from the table
            # The table rows are usually in tbody tr
            rows = page.query_selector_all('tbody.MuiTableBody-root tr')
            print(f"[CodeChef List] Found {len(rows)} potential problems on page.")

            for i, row in enumerate(rows):
                try:
                    # Column 0: Code (e.g., MISINTER)
                    # Column 1: Name (e.g., Misinterpretation)
                    # Column 3: Difficulty (e.g., 1632)
                    
                    code_el = row.query_selector('td:nth-child(1)')
                    if not code_el:
                        continue
                    code = code_el.inner_text().strip()
                    
                    if not code:
                        continue

                    # Construct URL
                    problem_url = f"{base_url}/problems/{code}"
                    
                    name_el = row.query_selector('td:nth-child(2)')
                    title = name_el.inner_text().strip() if name_el else code
                    
                    # Difficulty is in 4th column (index 3 if 0-indexed, but nth-child is 1-indexed)
                    # The HTML shows data-colindex="3" which is the 4th column.
                    diff_el = row.query_selector('td:nth-child(4)')
                    difficulty = diff_el.inner_text().strip() if diff_el else "0"

                    scraped_data.append({
                        "title": title,
                        "url": problem_url,
                        "difficulty": difficulty,
                        "tag": tag,
                        "platform": "CodeChef"
                    })
                except Exception as e:
                    print(f"[CodeChef List] Error extracting row: {e}")
                    continue

        except Exception as e:
            print(f"[CodeChef List] Error on list page: {e}")
            browser.close()
            return []

        print(f"[CodeChef List] Found {len(scraped_data)} unique problems. Starting details...")

        # Detail Scraping
        for item in scraped_data:
            try:
                print(f"[CodeChef Detail] Scraping details for: {item['title']}")
                detail_page = context.new_page()
                detail_page.goto(item["url"], wait_until="domcontentloaded", timeout=60000)
                
                # Wait for problem statement content
                # CodeChef uses specific IDs or classes for the statement
                # Often it's in a div with id matching 'problem-statement' or similar class
                try:
                    detail_page.wait_for_selector('div#problem-statement', timeout=15000)
                    content_el = detail_page.query_selector('div#problem-statement')
                except:
                    # Fallback for newer UI or different structure
                    # Look for the main content area
                    try:
                         detail_page.wait_for_selector('div[class*="ProblemStatement_problemStatement"]', timeout=10000)
                         content_el = detail_page.query_selector('div[class*="ProblemStatement_problemStatement"]')
                    except:
                        print(f"[CodeChef Detail] Content container not found for {item['title']}")
                        detail_page.close()
                        continue

                raw_text = content_el.inner_text() if content_el else ""
                
                # Regex patterns for headers
                # We look for "Input Format", "Input:", "Output Format", "Output:", "Constraints", "Sample"
                # We want to find the FIRST occurrence of any of these to cut off the description.
                
                headers_pattern = r'(Input(?:\s+Format|)|Output(?:\s+Format|)|Constraints|Sample\s+\d+|Explanation|Note:)'
                
                # Split the text by the first header found to get the clean description
                split_match = re.search(headers_pattern, raw_text, re.IGNORECASE)
                
                if split_match:
                    item["description"] = clean_text(raw_text[:split_match.start()])
                else:
                    item["description"] = clean_text(raw_text)

                # Now extract specific sections using regex as before, but maybe more robustly
                input_match = re.search(r'Input(?:\s+Format|):?(.+?)(?=Output|Constraints|Sample|Explanation)', raw_text, re.DOTALL | re.IGNORECASE)
                item["input_format"] = clean_text(input_match.group(1)) if input_match else ""
                
                output_match = re.search(r'Output(?:\s+Format|):?(.+?)(?=Constraints|Sample|Explanation|Input)', raw_text, re.DOTALL | re.IGNORECASE)
                item["output_format"] = clean_text(output_match.group(1)) if output_match else ""
                
                constraints_match = re.search(r'Constraints:?(.+?)(?=Sample|Explanation|Input|Output)', raw_text, re.DOTALL | re.IGNORECASE)
                item["constraints"] = clean_text(constraints_match.group(1)) if constraints_match else ""
                
                # Extract samples
                # We want to preserve newlines for samples so they are readable
                # The regex needs to be careful not to consume the next section
                samples_match = re.findall(r'(Sample\s+\d+:?)(.+?)(?=Explanation|Note:|$)', raw_text, re.DOTALL | re.IGNORECASE)
                samples = []
                for sm in samples_match:
                    header = sm[0].strip()
                    content = sm[1]
                    
                    # Clean content but preserve newlines
                    # specialized clean: remove carriage returns, keep \n, collapse multiple spaces to 1 but keep \n
                    content_clean = re.sub(r'[ \t]+', ' ', content) # collapse spaces on a line
                    content_clean = re.sub(r'\n\s*\n', '\n', content_clean) # remove empty lines
                    content_clean = content_clean.strip()
                    
                    samples.append(f"{header}\n{content_clean}")
                
                item["samples"] = samples
                
                # Extract Explanation
                explanation_match = re.search(r'Explanation:?(.+)', raw_text, re.DOTALL | re.IGNORECASE)
                if explanation_match:
                     expl_text = explanation_match.group(1)
                     item["explanation"] = re.sub(r'\s+', ' ', expl_text).strip()
                else:
                    item["explanation"] = ""

                detail_page.close()
                time.sleep(1) 

            except Exception as e:
                print(f"[CodeChef Detail] Error details for {item['title']}: {e}")
                try:
                    detail_page.close()
                except:
                    pass

        browser.close()
    
    # transform keys to match user request more closely if needed, 
    # but keeping snake_case is standard for code. 
    # The user asked for "Input", "Output" etc in the list, we can keep json keys simple.
    return scraped_data

if __name__ == "__main__":
    # Test execution
    data = scrape_codechef_questions("permutation-cycles")
    import json
    print(json.dumps(data, indent=2))
