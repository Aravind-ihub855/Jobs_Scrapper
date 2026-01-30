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
            
            # 2. Navigate to search for more problems (prioritize search for topics/tags)
            try:
                search_url = f"https://www.interviewbit.com/search/?q={query}"
                print(f"[InterviewBit] Navigating to search URL for rich metadata: {search_url}")
                page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
                
                # Check if we landed on search or redirect
                if "/search/" not in page.url:
                    # Try to find a link if redirect happened to landing page
                    view_all_link = page.locator("a:has-text('View All Problems')").first
                    if view_all_link.count() > 0 and view_all_link.is_visible(timeout=5000):
                        print("[InterviewBit] Redirected. Clicking 'View All Problems'...")
                        view_all_link.click()
                        page.wait_for_load_state("domcontentloaded")
                
                time.sleep(2)
            except Exception as e:
                print(f"[InterviewBit] Navigation to search list failed: {e}. Trying landing page fallback.")
                page.goto(url, wait_until="domcontentloaded", timeout=60000)

            # 3. Locate Coding Problems / Search results
            print("[InterviewBit] extracting problem links...")
            
            # This logic works for both the landing page and the search results page (accordions)
            problem_links = page.evaluate("""() => {
                const results = [];
                
                // 1. Check for standard landing page links
                const landingDivs = Array.from(document.querySelectorAll('.problem-tile, .article-problems__list-tile, #problem-widget-tile'));
                landingDivs.forEach(div => {
                    const a = div.querySelector('a') || (div.tagName === 'A' ? div : null);
                    if (!a || !a.href || a.href.includes('/solve')) return;
                    
                    const url = a.href;
                    // Robust Title extraction: clone and strip junk labels/tags
                    const clone = a.cloneNode(true);
                    const junk = clone.querySelectorAll('.label, .tag, .company-tag, span, i');
                    junk.forEach(el => el.remove());
                    const title = clone.innerText.trim() || clone.textContent.trim() || "Coding Problem";
                    
                    // Try to finding topic from parent section
                    let topic = "";
                    const section = div.closest('section, .article-problems__list, .article-problems');
                    if (section) {
                        const header = section.querySelector('h2, h3, .section-title');
                        if (header) topic = header.innerText.trim();
                    }

                    if (url && !results.some(r => r.url === url)) {
                        results.push({ title, url, topic, search_tags: [] });
                    }
                });

                // 2. Check for Search Page structure (accordions + "Go To Problem" buttons)
                const panels = Array.from(document.querySelectorAll('.panel-group, .panel, .panel-default'));
                panels.forEach(panel => {
                    const btn = panel.querySelector('a[href*="/problems/"]');
                    if (!btn || !btn.innerText.includes('Go To Problem')) return;

                    const url = btn.href;
                    
                    // Extract Title from header - exclude tags/labels via cloning
                    const header = panel.querySelector('.panel-heading, h3, a[data-toggle="collapse"]');
                    let title = "Coding Problem";
                    if (header) {
                        const clone = header.cloneNode(true);
                        const junk = clone.querySelectorAll('.label, .tag, .company-tag, span, i');
                        junk.forEach(el => el.remove());
                        title = clone.innerText.trim() || clone.textContent.trim() || "Coding Problem";
                    }
                    
                    // Extract Topic/Category from the preceding h3 on search page
                    let topic = "";
                    const parent = panel.closest('.panel-group, #accordion');
                    let prev = parent ? parent.previousElementSibling : panel.previousElementSibling;
                    
                    while (prev) {
                        if (['H1', 'H2', 'H3', 'H4'].includes(prev.tagName)) {
                            topic = prev.innerText.trim();
                            break;
                        }
                        const heading = prev.querySelector('h1, h2, h3, h4');
                        if (heading) {
                            topic = heading.innerText.trim();
                            break;
                        }
                        prev = prev.previousElementSibling;
                    }

                    // Extract Tags (company labels next to title)
                    const tags = Array.from(panel.querySelectorAll('.label, .tag, .company-tag'))
                                      .map(t => t.innerText.trim())
                                      .filter(t => {
                                          const low = t.toLowerCase();
                                          const ignore = ["easy", "medium", "hard", "solved", "unsolved", "desktop", "smiley", "auth", "scaler", "submission"];
                                          return t && !ignore.some(x => low.includes(x)) && t.length < 30;
                                      });

                    if (url && !results.some(r => r.url === url)) {
                        results.push({ title, url, topic, search_tags: tags });
                    }
                });

                return results;
            }""")
            
            # Filter out duplicates and ensure URL is valid
            unique_problems = {}
            for item in problem_links:
                if "/problems/" in item['url'] and item['title']:
                    unique_problems[item['url']] = item
            
            print(f"[InterviewBit] Found {len(unique_problems)} unique problems.")
            
            count = 0
            for problem_url, info in unique_problems.items():
                problem_title = info['title']
                search_topic = info.get('topic', "Coding Problem")
                search_tags = info.get('search_tags', [])
                if count >= limit:
                    break
                
                # Avoid duplicates in the list if URL appears again in the same run
                if any(q['url'] == problem_url for q in scraped_data):
                    continue

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
                        "topic": search_topic,
                        "description": "",
                        "constraints": "",
                        "input_format": "",
                        "output_format": "",
                        "difficulty": "",
                        "success_rate": "",
                        "asked_in": search_tags,
                        "examples": []
                    }

                    # Extract Success Rate and Difficulty from the header area
                    try:
                        # Use JS to find Success Rate reliably
                        stats = problem_page.evaluate("""() => {
                            const spans = Array.from(document.querySelectorAll('span, div, p'));
                            const successMatch = spans.find(s => /\\d+\\.?\\d*% Success/.test(s.innerText));
                            const difficultyTags = document.querySelectorAll('span[class*="DifficultyTag"], .c-difficulty-tag');
                            
                            let difficulty = "";
                            if (difficultyTags.length > 0) {
                                difficulty = difficultyTags[0].innerText.trim();
                            } else {
                                const dMatch = spans.find(s => ["Easy", "Medium", "Hard"].includes(s.innerText.trim()));
                                if (dMatch) difficulty = dMatch.innerText.trim();
                            }

                            return {
                                success: successMatch ? successMatch.innerText.trim() : "",
                                difficulty: difficulty
                            };
                        }""")
                        problem_data["success_rate"] = stats["success"]
                        if stats["difficulty"]:
                            problem_data["difficulty"] = stats["difficulty"]
                    except:
                        pass
                    
                    # Extract "Asked In" companies from logos and merge with search tags
                    try:
                        companies = list(search_tags)
                        # Selector for the "Asked In" container images
                        asked_in_section = problem_page.locator("div:has-text('Asked In:'), .asked-in-logo").first
                        if asked_in_section.count() > 0:
                            imgs = asked_in_section.locator("img")
                            for i in range(imgs.count()):
                                img = imgs.nth(i)
                                name = img.get_attribute("title") or img.get_attribute("alt")
                                if not name:
                                    src = img.get_attribute("src")
                                    if src:
                                        match = re.search(r'/([^/.]+)\.(svg|png|jpg)', src)
                                        if match: name = match.group(1).title()
                                
                                if name:
                                    clean_name = name.replace(" logo", "").replace("-", " ").strip().lower()
                                    # Filter out non-company logos
                                    ignore_list = ["auth", "scaler", "superman", "icon", "vector", "logo", "desktop", "smiley", "submission", "interviewbit"]
                                    if not any(x in clean_name for x in ignore_list):
                                        companies.append(name.replace(" logo", "").strip())
                        
                        problem_data["asked_in"] = list(set(companies))
                    except:
                        pass
                    
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

                    if any(item['url'] == problem_url for item in scraped_data):
                        continue
                        
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
