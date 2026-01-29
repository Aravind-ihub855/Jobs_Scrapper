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
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        try:
            print(f" Navigating to problem list: {base_url}")
            # Use 'domcontentloaded' instead of 'networkidle' to be more resilient
            page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
            
            # Wait for specific link selector
            try:
                page.wait_for_selector('a[href*="/problems/"]', timeout=30000)
            except:
                print(" List links did not appear in time. Capturing what's available.")
            
            # Small buffer for list hydration
            time.sleep(3)
            
            links = page.query_selector_all('a[href*="/problems/"]')
            print(f" Found {len(links)} potential links")

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
                            "url": full_url,
                            "title": title,
                            "difficulty": difficulty,
                            "acceptance_rate": acceptance
                        })
                except Exception as e:
                    print(f" Error parsing list item: {e}")

            print(f" Found {len(question_links)} unique questions. Starting detailed scrape...")

            for q in question_links:
                try:
                    print(f" Scraping details for: {q['title']}")
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
                                constraints: []
                            };
                            
                            const children = Array.from(container.children);
                            let currentSection = 'description';

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

                            for (const child of children) {
                                const text = child.innerText.trim();
                                const isHeader = child.tagName === 'P' && (child.querySelector('strong') || child.querySelector('b'));
                                
                                if (isHeader) {
                                    if (/^Constraints:$/i.test(text)) {
                                        currentSection = 'constraints';
                                        continue;
                                    } else if (/^Example \d+:$/i.test(text)) {
                                        currentSection = 'examples';
                                        continue; // Skip the header itself
                                    }
                                }

                                if (child.tagName === 'PRE') {
                                    res.examples.push(text);
                                } else if (currentSection === 'examples') {
                                    // Capture example content even if not in PRE tags
                                    if (text && !text.startsWith('Example')) {
                                        res.examples.push(text);
                                    }
                                } else if (currentSection === 'description') {
                                    res.description.push(text);
                                } else if (currentSection === 'constraints') {
                                    // Use the helper function to preserve superscript notation
                                    res.constraints.push(convertSupToCaretNotation(child));
                                }
                            }
                            
                            // Extract topics - try multiple selectors
                            const topics = [];
                            // Try different possible selectors for topics
                            let topicElements = document.querySelectorAll('a[href*="/tag/"]');
                            if (topicElements.length === 0) {
                                topicElements = document.querySelectorAll('div[class*="topic"] a, a[class*="topic"]');
                            }
                            topicElements.forEach(el => {
                                const topic = el.innerText.trim();
                                if (topic && !topics.includes(topic) && topic.length > 0 && topic.length < 50) {
                                    topics.push(topic);
                                }
                            });
                            
                            return {
                                description_text: res.description.join('\\n').trim(),
                                examples: res.examples,
                                constraints: res.constraints,
                                topics: topics
                            };
                        }
                    """)

                    if details:
                        # Reconstruct in desired order: url, title, difficulty, acceptance_rate, description, examples, constraints, topics, source, slug
                        q_ordered = {
                            "url": q["url"],
                            "title": q["title"],
                            "difficulty": q["difficulty"],
                            "acceptance_rate": q["acceptance_rate"],
                            "description": details["description_text"],
                            "examples": details["examples"],
                            "constraints": details["constraints"],
                            "topics": details["topics"],
                            "source": "LeetCode",
                            "slug": problem_list_slug
                        }
                        # Replace the original dict with ordered one
                        q.clear()
                        q.update(q_ordered)
                    
                    time.sleep(2)
                except Exception as e:
                    print(f" Error scraping {q['title']}: {e}")
                    # Even if detail fails, we keep what we have from the list view
            
            return question_links

        except Exception as e:
            print(f" Global Error: {e}")
            return []
        finally:
            browser.close()
