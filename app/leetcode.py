from playwright.sync_api import sync_playwright
import time
import re

def scrape_leetcode_questions(problem_list_slug: str):
    """
    Scrapes LeetCode questions from a problem list slug (e.g., 'iterator').
    Improved version with better timeout handling and robust element waiting.
    """
    base_url = f"https://leetcode.com/problem-list/{problem_list_slug}/"
    questions = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        try:
            print(f"🔍 Navigating to problem list: {base_url}")
            # Use 'domcontentloaded' instead of 'networkidle' to be more resilient
            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for specific link selector
            try:
                page.wait_for_selector('a[href*="/problems/"]', timeout=30000)
            except:
                print("⚠️ List links did not appear in time. Capturing what's available.")
            
            # Small buffer for list hydration
            time.sleep(3)
            
            links = page.query_selector_all('a[href*="/problems/"]')
            print(f"✅ Found {len(links)} potential links")

            question_links = []
            for link in links:
                try:
                    href = link.get_attribute("href")
                    if not href or "/problems/" not in href:
                        continue
                    
                    clean_href = href.split('?')[0]
                    full_url = f"https://leetcode.com{clean_href}" if clean_href.startswith('/') else clean_href
                    
                    if full_url.count('/') < 4:
                        continue

                    title_el = link.query_selector('div.truncate')
                    title = title_el.inner_text().strip() if title_el else link.inner_text().split('\n')[0].strip()

                    difficulty = "N/A"
                    diff_el = link.query_selector('p')
                    if diff_el:
                        difficulty = diff_el.inner_text().strip()

                    acceptance = "N/A"
                    divs = link.query_selector_all('div')
                    for d in divs:
                        txt = d.inner_text().strip()
                        if '%' in txt and len(txt) < 10:
                            acceptance = txt
                            break

                    if not any(q['url'] == full_url for q in question_links):
                        question_links.append({
                            "title": title,
                            "url": full_url,
                            "difficulty": difficulty,
                            "acceptance_rate": acceptance
                        })
                except Exception as e:
                    print(f"⚠️ Error parsing list item: {e}")

            print(f"🚀 Found {len(question_links)} unique questions. Starting detailed scrape...")

            for q in question_links:
                try:
                    print(f"➡️ Scraping details for: {q['title']}")
                    # Use 'domcontentloaded' and increased timeout (45s) for reliability
                    page.goto(q['url'], wait_until="domcontentloaded", timeout=45000)
                    
                    # Explicitly wait for the container we need
                    page.wait_for_selector('div[data-track-load="description_content"]', timeout=30000)
                    
                    details = page.evaluate("""
                        () => {
                            const container = document.querySelector('div[data-track-load="description_content"]');
                            if (!container) return null;

                            const res = { 
                                description: [], 
                                examples: [], 
                                constraints: [], 
                                follow_up: [] 
                            };
                            
                            const children = Array.from(container.children);
                            let currentSection = 'description';

                            for (const child of children) {
                                const text = child.innerText.trim();
                                const isHeader = child.tagName === 'P' && (child.querySelector('strong') || child.querySelector('b'));
                                
                                if (isHeader) {
                                    if (/^Constraints:$/i.test(text)) {
                                        currentSection = 'constraints';
                                        continue;
                                    } else if (/^Follow up:$/i.test(text)) {
                                        currentSection = 'follow_up';
                                        continue;
                                    } else if (/^Example \d+:$/i.test(text)) {
                                        currentSection = 'examples';
                                    }
                                }

                                if (child.tagName === 'PRE') {
                                    res.examples.push(text);
                                } else if (currentSection === 'description') {
                                    res.description.push(text);
                                } else if (currentSection === 'constraints') {
                                    res.constraints.push(text);
                                } else if (currentSection === 'follow_up') {
                                    res.follow_up.push(text);
                                }
                            }
                            
                            return {
                                description_text: res.description.join('\\n').trim(),
                                examples: res.examples,
                                constraints: res.constraints,
                                follow_up: res.follow_up.join('\\n').trim()
                            };
                        }
                    """)

                    if details:
                        q.update({
                            "description": details["description_text"],
                            "examples": details["examples"],
                            "constraints": details["constraints"],
                            "follow_up": details["follow_up"],
                            "source": "LeetCode",
                            "slug": problem_list_slug
                        })
                    
                    time.sleep(2)
                except Exception as e:
                    print(f"❌ Error scraping {q['title']}: {e}")
                    # Even if detail fails, we keep what we have from the list view
            
            return question_links

        except Exception as e:
            print(f"❌ Global Error: {e}")
            return []
        finally:
            browser.close()
