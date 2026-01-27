from playwright.sync_api import sync_playwright
import re
import time

def clean_text(text: str) -> str:
    """Removes extra whitespace and normalizes text."""
    if not text:
        return ""
    text = text.encode('ascii', 'ignore').decode('ascii')
    return re.sub(r'\s+', ' ', text).strip()

def scrape_interviewbit_questions(query: str, limit: int = 5):
    """
    Scrapes interview questions from InterviewBit for a specific company or topic.
    
    Args:
        query: Company name or topic (e.g., 'amazon', 'google', 'facebook').
        limit: Maximum number of problems to scrape.
    """
    scraped_data = []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()
        
        try:
            # 1. Navigate to the Interview Questions page
            # URL pattern: https://www.interviewbit.com/{query}-interview-questions/
            # Ensure query is url-friendly (lowercase, slugified)
            slug = query.lower().replace(" ", "-")
            url = f"https://www.interviewbit.com/{slug}-interview-questions/"
            print(f"[InterviewBit] Navigating to {url}")
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # 2. Locate Coding Problems section
            print("[InterviewBit] Looking for 'Coding Problems' section...")
            try:
                # Click "Coding Problems" to ensure it's open
                try:
                    coding_problems_header = page.locator("text=Coding Problems")
                    if coding_problems_header.is_visible(timeout=5000):
                        coding_problems_header.scroll_into_view_if_needed()
                        coding_problems_header.click()
                        print("[InterviewBit] Clicked 'Coding Problems'")
                        time.sleep(1)
                except:
                    pass

                # Expand all sub-categories to ensure all links are rendered
                categories = ["Easy Problems", "Medium Problems", "Hard Problems", "Intermediate Problems", "Advanced Problems"]
                for cat in categories:
                    try:
                        header = page.locator(f"text={cat}")
                        if header.count() > 0 and header.first.is_visible():
                            header.first.click(timeout=2000)
                            print(f"[InterviewBit] Clicked '{cat}'")
                            time.sleep(1)
                    except:
                        pass
                
                # Wait for at least some problem links
                page.wait_for_selector('a[href*="/problems/"]', timeout=5000)
                
            except Exception as e:
                print(f"[InterviewBit] formatting/interaction check failed: {e}. Trying to extract links anyway.")

            
            # Find all problem links.
            print("[InterviewBit] extracting problem links...")
            
            # This selector seeks anchor tags pointing to /problems/
            # We explicitly ignore "solve" buttons if they exist and just get the main link
            problem_links = page.evaluate("""() => {
                const links = Array.from(document.querySelectorAll('a[href*="/problems/"]'));
                return links.map(a => ({
                    title: a.innerText.trim(),
                    url: a.href
                })).filter(item => item.title && !item.url.includes('/solve')); 
            }""")
            
            # Filter out duplicates
            unique_problems = {}
            for item in problem_links:
                if "/problems/" in item['url']:
                    unique_problems[item['url']] = item['title']
            
            print(f"[InterviewBit] Found {len(unique_problems)} unique problems.")
            
            count = 0
            for problem_url, problem_title in unique_problems.items():
                if count >= limit:
                    break
                
                print(f"[InterviewBit] Scraping problem: {problem_title}")
                
                try:
                    problem_page = context.new_page()
                    problem_page.goto(problem_url, wait_until="domcontentloaded", timeout=60000)
                    
                    # Wait for content - Improved Strategy
                    print(f"[InterviewBit] Waiting for content on {problem_url}")
                    content_element = None
                    try:
                        # Wait for the description specifically
                        # Based on debug, 'Problem Description' text exists
                        # Container classes from debug: 'p-markdown', 'class-p-markdown', 'markdown-content-container'
                        # or 'problem-content' or just 'p-html'
                        
                        # First, handle potential tabs. Ensure 'Description' is active.
                        try:
                            desc_tab = problem_page.locator("li:has-text('Description')")
                            if desc_tab.count() > 0:
                                desc_tab.click(timeout=1000)
                        except:
                            pass
                        
                        selectors = [
                            'div.markdown-content-container',
                            'div.p-markdown', 
                            '#problem-content',
                            'div.problem_description', 
                            'div.problem-statement'
                        ]
                        
                        # Wait a bit longer for SPA rendering
                        problem_page.wait_for_timeout(3000)
                        
                        for sel in selectors:
                            try:
                                if problem_page.locator(sel).first.is_visible(timeout=3000):
                                    content_element = problem_page.query_selector(sel)
                                    print(f"[InterviewBit] Found content with selector: {sel}")
                                    break
                            except:
                                continue
                        
                        if not content_element:
                            print("[InterviewBit] Specific selectors failed. Trying text-based location...")
                            # Look for the header "Problem Description"
                            try:
                                header = problem_page.locator("text=Problem Description").first
                                if header.is_visible(timeout=5000):
                                    # The content is usually in the parent or next sibling
                                    # Let's try to get a parent container
                                    # .xpath('..') might work or just using the parent div
                                    content_element = header.locator("xpath=../..").element_handle()
                                    if not content_element:
                                         content_element = problem_page.query_selector('body')
                                    print(f"[InterviewBit] Located content via text header.")
                                else:
                                     # Last resort: body
                                     content_element = problem_page.query_selector('body')
                                     print(f"[InterviewBit] Fallback to body.")
                            except:
                                pass
                    except:
                        pass

                    if not content_element:
                         print(f"[InterviewBit] Failed to locate content for {problem_title}")
                         problem_page.close()
                         continue
                    
                    # Initialize problem_data
                    problem_data = {
                        "title": problem_title,
                        "url": problem_url,
                        "platform": "InterviewBit",
                        "company": query,
                        "description": "",
                        "constraints": "",
                        "input_format": "",
                        "output_format": "",
                        "examples": []
                    }
                    
                    # Pre-process superscripts to verify readability (e.g., 10^5 instead of 105)
                    try:
                        content_element.evaluate("""(el) => {
                            const sups = el.querySelectorAll('sup');
                            sups.forEach(s => {
                                if (!s.innerText.startsWith('^')) {
                                    s.innerText = '^' + s.innerText;
                                }
                            });
                        }""")
                    except Exception as e:
                        print(f"[InterviewBit] formatting superscripts failed: {e}")

                    # Clean the title if it contains newlines or extra spaces (common if link wraps a card)
                    clean_title = clean_text(problem_title)
                    # Often the title might look like "Problem Name\nEasy..." because the link wraps the whole card
                    # We can try to take just the first line or a substring
                    if '\n' in problem_title or '  ' in problem_title:
                         # Heuristic: the title is usually the first non-empty line or segment
                         parts = [p.strip() for p in problem_title.split('\n') if p.strip()]
                         if parts:
                             clean_title = parts[0]
                    
                    problem_data["title"] = clean_title # Update with cleaner title
                    
                    if content_element:
                        raw_text = content_element.inner_text()
                        # print(f"[InterviewBit] Debug Raw Text Sample: {raw_text[:200]}")
                        
                        # Parse sections using regex or splitting
                        # Common headers: "Problem Description", "Problem Constraints", "Input Format", "Output Format", "Example Input", "Example Output", "Example Explanation"
                        
                        # Description
                        # Locate "Problem Description" and take text until "Problem Constraints"
                        desc_parts = re.split(r'Problem Constraints|Input Format', raw_text)
                        if len(desc_parts) > 0:
                             raw_desc = desc_parts[0]
                             problem_data['description'] = clean_text(raw_desc.replace("Problem Description", ""))
                        
                        # Constraints
                        constraints_match = re.search(r'Problem Constraints\s*(.*?)(?=Input Format|Output Format|Example Input)', raw_text, re.DOTALL)
                        if constraints_match:
                            problem_data['constraints'] = clean_text(constraints_match.group(1))
                            
                        # Input Format
                        input_match = re.search(r'Input Format\s*(.*?)(?=Output Format|Example Input)', raw_text, re.DOTALL)
                        if input_match:
                            problem_data['input_format'] = clean_text(input_match.group(1))

                        # Output Format
                        output_match = re.search(r'Output Format\s*(.*?)(?=Example Input|Example Output)', raw_text, re.DOTALL)
                        if output_match:
                            problem_data['output_format'] = clean_text(output_match.group(1))

                        # Examples
                        # This part is tricky as there might be multiple examples.
                        # For now, let's try to capture the first one or the block.
                        ex_input_match = re.search(r'Example Input\s*(.*?)(?=Example Output)', raw_text, re.DOTALL)
                        ex_output_match = re.search(r'Example Output\s*(.*?)(?=Example Explanation|$)', raw_text, re.DOTALL)
                        ex_explanation_match = re.search(r'Example Explanation\s*(.*?)(?=$)', raw_text, re.DOTALL)
                        
                        example = {
                            "input": clean_text(ex_input_match.group(1)) if ex_input_match else "",
                            "output": clean_text(ex_output_match.group(1)) if ex_output_match else "",
                            "explanation": clean_text(ex_explanation_match.group(1)) if ex_explanation_match else ""
                        }
                        
                        if example['input'] or example['output']:
                            problem_data['examples'].append(example)

                    scraped_data.append(problem_data)
                    count += 1
                    problem_page.close()
                    time.sleep(1)
                    
                except Exception as e:
                    import traceback
                    print(f"[InterviewBit] Error scraping problem {problem_title}: {e}")
                    traceback.print_exc()
                    try:
                        problem_page.close()
                    except:
                        pass
                        
        except Exception as e:
            print(f"[InterviewBit] Error in main scrape loop: {e}")
        
        browser.close()
        
    return scraped_data
