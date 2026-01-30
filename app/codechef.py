from playwright.sync_api import sync_playwright
import re
import time

def clean_text(text: str) -> str:
    """Removes extra whitespace from text."""
    if not text:
        return ""
    return re.sub(r'\s+', ' ', text).strip()

def scrape_codechef_questions(tag: str = None, topic: str = None, pages: int = 1):
    """
    Scrapes CodeChef questions for a specific tag or topic using Playwright.
    """
    scraped_data = []
    base_url = "https://www.codechef.com"
    
    if topic:
        list_url = f"{base_url}/practice-old/topics/{topic}"
    elif tag:
        list_url = f"{base_url}/practice-old/tags/{tag}"
    else:
        print("[CodeChef List] Error: No tag or topic provided.")
        return []

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
            
            # Detection of total pages if pages=0 or for logging
            total_pages = pages
            try:
                # Look for text like "1-20 of 224"
                pagination_text_el = page.query_selector('p[class*="MuiTablePagination-displayedRows"]')
                if pagination_text_el:
                    pagination_text = pagination_text_el.inner_text()
                    # Extract 224 from "1-20 of 224"
                    total_match = re.search(r'of\s+(\d+)', pagination_text)
                    if total_match:
                        total_items = int(total_match.group(1))
                        # Assuming 20 rows per page (default)
                        total_pages_detected = (total_items + 19) // 20
                        print(f"[CodeChef List] Detected {total_items} items across {total_pages_detected} pages.")
                        if pages == 0:
                            total_pages = total_pages_detected
            except Exception as pe:
                print(f"[CodeChef List] Could not detect total pages: {pe}")

            # If pages is still 0 (and detection failed), we'll just loop indefinitely until next is disabled
            max_loop = total_pages if total_pages > 0 else 9999 

            for current_page_num in range(1, max_loop + 1):
                print(f"[CodeChef List] Scraping page {current_page_num}...")
                
                # Wait for the table to load
                page.wait_for_selector('table.MuiTable-root', timeout=20000)
                
                # Extract problems from the table
                rows = page.query_selector_all('tbody.MuiTableBody-root tr')
                print(f"[CodeChef List] Found {len(rows)} potential problems on page {current_page_num}.")

                for i, row in enumerate(rows):
                    try:
                        row_text = row.inner_text().lower()
                        if "becoming the best coder" in row_text:
                            continue

                        code_el = row.query_selector('td:nth-child(1)')
                        if not code_el:
                            continue
                        code = code_el.inner_text().strip()
                        
                        if not code:
                            continue

                        # Construct URL
                        problem_url = f"{base_url}/problems/{code}"
                        
                        # Avoid duplicates in the list
                        if any(item['url'] == problem_url for item in scraped_data):
                            continue

                        name_el = row.query_selector('td:nth-child(2)')
                        title = name_el.inner_text().strip() if name_el else code
                        
                        diff_el = row.query_selector('td:nth-child(4)')
                        difficulty = diff_el.inner_text().strip() if diff_el else "0"

                        scraped_data.append({
                            "title": title,
                            "url": problem_url,
                            "difficulty": difficulty,
                            "tag": tag,
                            "topic": topic,
                            "platform": "CodeChef"
                        })
                    except Exception as e:
                        print(f"[CodeChef List] Error extracting row: {e}")
                        continue

                # Pagination logic: Check if we need more pages and if a next button exists
                if pages == 0 or current_page_num < pages:
                    # Get the current first problem code to verify change after click
                    first_code_before = None
                    try:
                        first_row = page.query_selector('tbody.MuiTableBody-root tr')
                        if first_row:
                            code_el = first_row.query_selector('td:nth-child(1)')
                            if code_el:
                                first_code_before = code_el.inner_text().strip()
                    except:
                        pass

                    # Try multiple selectors for the next button
                    next_button = None
                    next_selectors = [
                        'button:has(svg[data-testid="KeyboardArrowRightIcon"])',
                        'button:has(svg[data-testid="NavigateNextIcon"])',
                        'button[aria-label="Next page"]',
                        'button[aria-label="Go to next page"]',
                        'nav[aria-label="pagination navigation"] button:has(svg[data-testid="KeyboardArrowRightIcon"])',
                        'nav[aria-label="pagination navigation"] button:has(svg[data-testid="NavigateNextIcon"])',
                        'button[aria-label*="next" i]',
                        'button[aria-label*="Next" i]'
                    ]
                    
                    for sel in next_selectors:
                        next_button = page.query_selector(sel)
                        if next_button:
                            break
                    
                    # Check if button is disabled (MUI uses both 'disabled' attribute and 'Mui-disabled' class)
                    is_disabled = page.evaluate("""(btn) => {
                        if (!btn) return true;
                        return btn.disabled || btn.classList.contains('Mui-disabled') || btn.getAttribute('aria-disabled') === 'true';
                    }""", next_button)
                    
                    if next_button and not is_disabled:
                        print(f"[CodeChef List] Clicking next page (after page {current_page_num})...")
                        
                        # Scroll into view to ensure it's clickable
                        next_button.scroll_into_view_if_needed()
                        next_button.click()
                        
                        # Wait for the first code to change, indicating a new page has loaded
                        if first_code_before:
                            try:
                                page.wait_for_function(
                                    f"() => {{ \
                                        const el = document.querySelector('tbody.MuiTableBody-root tr td:nth-child(1)'); \
                                        return el && el.innerText.trim() !== '{first_code_before}'; \
                                }}", timeout=15000
                                )
                                print(f"[CodeChef List] Page {current_page_num + 1} transition detected. Waiting for stability...")
                                # Additional sleep to ensure all rows are rendered
                                time.sleep(2)
                            except:
                                print(f"[CodeChef List] Timeout waiting for page {current_page_num + 1} to load, continuing...")
                                time.sleep(3)
                        else:
                            time.sleep(4) 
                    else:
                        print("[CodeChef List] No more pages available or Next button disabled.")
                        break

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

                # Use evaluate to get text and handle superscripts
                raw_text = detail_page.evaluate("""
                    () => {
                        const contentEl = document.querySelector('div#problem-statement') || 
                                          document.querySelector('div[class*="ProblemStatement_problemStatement"]');
                        if (!contentEl) return "";

                        const clone = contentEl.cloneNode(true);
                        const sups = clone.querySelectorAll('sup');
                        sups.forEach(sup => {
                            const text = sup.textContent;
                            sup.replaceWith(`^${text}`);
                        });
                        return clone.innerText;
                    }
                """)
                
                # Regex patterns for headers
                # We look for "Input Format", "Input:", "Output Format", "Output:", "Constraints", "Sample"
                # We want to find the FIRST occurrence of any of these to cut off the description.
                
                headers_pattern = r'(Input(?:\s+Format|)|Output(?:\s+Format|)|Constraints|Subtasks|Sample\s+\d+|Explanation|Note:)'
                
                # Split the text by the first header found to get the clean description
                split_match = re.search(headers_pattern, raw_text, re.IGNORECASE)
                
                if split_match:
                    item["description"] = clean_text(raw_text[:split_match.start()])
                else:
                    item["description"] = clean_text(raw_text)

                # Now extract specific sections using regex
                input_match = re.search(r'Input(?:\s+Format|):?(.+?)(?=Output|Constraints|Subtasks|Sample|Explanation)', raw_text, re.DOTALL | re.IGNORECASE)
                item["input_format"] = clean_text(input_match.group(1)) if input_match else ""
                
                output_match = re.search(r'Output(?:\s+Format|):?(.+?)(?=Constraints|Subtasks|Sample|Explanation|Input)', raw_text, re.DOTALL | re.IGNORECASE)
                item["output_format"] = clean_text(output_match.group(1)) if output_match else ""
                
                constraints_match = re.search(r'Constraints:?(.+?)(?=Subtasks|Sample|Explanation|Input|Output)', raw_text, re.DOTALL | re.IGNORECASE)
                item["constraints"] = clean_text(constraints_match.group(1)) if constraints_match else ""

                subtasks_match = re.search(r'Subtasks:?(.+?)(?=Sample|Explanation|Input|Output|Constraints)', raw_text, re.DOTALL | re.IGNORECASE)
                item["subtasks"] = clean_text(subtasks_match.group(1)) if subtasks_match else ""
                
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
