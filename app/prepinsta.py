from playwright.sync_api import sync_playwright
import re
import time

def clean_text(text: str) -> str:
    """Removes extra whitespace but keeps some structure."""
    if not text:
        return ""
    # Collapse multiple spaces
    text = re.sub(r'[ \t]+', ' ', text)
    # Collapse multiple newlines
    text = re.sub(r'\n\s*\n', '\n', text)
    return text.strip()

def scrape_prepinsta_questions(company: str = "capgemini"):
    """
    Scrapes questions from PrepInsta for a given company.
    """
    scraped_data = []
    url = f"https://prepinsta.com/{company}/coding-questions/"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use a realistic user agent
        context = browser.new_context(
             user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        print(f"[PrepInsta] Navigating to: {url}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Additional wait for content to settle
            time.sleep(3)
            
            # PrepInsta often puts questions in a main container.
            # Let's try to grab the main text content of the article/page
            # usually class='entry-content' or similar in WordPress, which PrepInsta likely uses.
            # Fallback to body to ensure we see everything
            content_el = page.query_selector('body')
            
            if not content_el:
                print("[PrepInsta] Could not find content container.")
                browser.close()
                return []

            raw_text = content_el.inner_text()
            
            # Limit search to the actual question area
            start_marker = "Practice Questions for Capgemini Exceller Coding Round"
            end_marker = "Prepare more coding questions"
            
            start_idx = raw_text.find(start_marker)
            end_idx = raw_text.find(end_marker)
            
            if start_idx != -1:
                # include the marker for splitting
                if end_idx != -1:
                    raw_text = raw_text[start_idx:end_idx]
                else:
                    raw_text = raw_text[start_idx:]
            
            # Split by "Question 1", "Question 2", etc.
            question_blocks = re.split(r'(?=\bQuestion\s+\d+)', raw_text)
            
            print(f"[PrepInsta] Found {len(question_blocks)} potential text blocks.")
            
            for block in question_blocks:
                block = block.strip()
                if not block.lower().startswith("question"):
                    continue
                
                # Extract Title (Question X)
                title_line = block.split('\n')[0].strip()
                title = re.sub(r'[:.]+$', '', title_line)
                
                sections = {
                   "problem_statement": "",
                   "input_format": "",
                   "output_format": "",
                   "sample_input": "",
                   "sample_output": ""
                }
                
                # Extract sections more robustly
                # Problem Statement –
                # Input :
                # Output :
                # Sample Input
                # Example :
                
                # We can find the headers and their indices
                headers = [
                    ("Problem Statement", r'Problem Statement\s*[-–:]?'),
                    ("Input", r'\bInput\s*[:]?'),
                    ("Output", r'\bOutput\s*[:]?'),
                    ("Sample Input", r'Sample Input|Sample Test Case'),
                    ("Example", r'Example\s*[:]?')
                ]
                
                found_headers = []
                for name, pattern in headers:
                    match = re.search(pattern, block, re.IGNORECASE)
                    if match:
                        found_headers.append((match.start(), match.end(), name))
                
                # Sort by start position
                found_headers.sort()
                
                # If no headers found, treat content after title as problem statement
                if not found_headers:
                    lines = block.split('\n')
                    if len(lines) > 1:
                        sections["problem_statement"] = "\n".join(lines[1:]).strip()
                else:
                    # Content before the first header (but after title)
                    first_header_start = found_headers[0][0]
                    title_len = len(title_line)
                    if first_header_start > title_len:
                        pre_content = block[title_len:first_header_start].strip()
                        if pre_content:
                            sections["problem_statement"] = pre_content
                    
                    # Extract contents between headers
                    for i in range(len(found_headers)):
                        start_pos = found_headers[i][1]
                        end_pos = found_headers[i+1][0] if i+1 < len(found_headers) else len(block)
                        header_name = found_headers[i][2]
                        content = block[start_pos:end_pos].strip()
                        
                        if header_name == "Problem Statement":
                            sections["problem_statement"] += ("\n" + content if sections["problem_statement"] else content)
                        elif header_name == "Input":
                            sections["input_format"] = content
                        elif header_name == "Output":
                            sections["output_format"] = content
                        elif header_name == "Sample Input":
                            sections["sample_input"] = content
                        elif header_name == "Example":
                            if not sections["sample_input"]:
                                sections["sample_input"] = content
                            else:
                                sections["problem_statement"] += "\nExample:\n" + content
                
                # Clean up extracted content
                for key in sections:
                    sections[key] = clean_text(sections[key])

                scraped_data.append({
                    "title": title,
                    "url": url,
                    "company": company,
                    "problem_statement": sections["problem_statement"],
                    "input": sections["input_format"],
                    "output": sections["output_format"],
                    "sample_input": sections["sample_input"],
                    "platform": "PrepInsta"
                })
                
        except Exception as e:
            print(f"[PrepInsta] Error scraping: {e}")
            
        browser.close()
        
    return scraped_data

if __name__ == "__main__":
    data = scrape_prepinsta_questions()
    import json
    print(json.dumps(data, indent=2))
