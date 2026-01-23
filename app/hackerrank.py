import re
import html
import requests
from typing import List, Optional
from html.parser import HTMLParser

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.output = []
        self.ignore_tags = {'style', 'script', 'head', 'meta', 'title'}
        self.current_tag = None
        self.ignore_depth = 0
    
    def handle_starttag(self, tag, attrs):
        if tag in self.ignore_tags:
            self.ignore_depth += 1
            
    def handle_endtag(self, tag):
        if tag in self.ignore_tags:
            self.ignore_depth -= 1
            
    def handle_data(self, data):
        if self.ignore_depth == 0 and data.strip():
            self.output.append(data.strip())
            
    def get_text(self):
        return " ".join(self.output)

def clean_html_content(html_content: str) -> str:
    if not html_content:
        return ""
    try:
        extractor = TextExtractor()
        extractor.feed(html_content)
        cleaned_text = extractor.get_text()
        
        # Additional cleanup for MathJax specifics if they leak through mechanism other than tags
        # (e.g. if they are in comments or weird structures, though proper tag ignoring should catch most)
        if "MathJax_SVG_Display" in cleaned_text:
             # Fallback regex for any lurking css blocks that might have been missed if HTML was malformed
             cleaned_text = re.sub(r'\.MathJax_SVG_Display\s*\{[^}]*\}', '', cleaned_text)
             cleaned_text = re.sub(r'\.MathJax_SVG\s*\{[^}]*\}', '', cleaned_text)
             
        return cleaned_text
    except Exception:
        # Fallback if parser fails on very bad HTML
        return html_content

def parse_hackerrank_description(html_content: str):
    """
    Parses the raw HTML description from HackerRank into structured fields
    using standard library tools to avoid extra dependencies.
    """
    if not html_content:
        return {}
        
    structured_data = {
        "description": "",
        "input_format": "",
        "output_format": "",
        "constraints": "",
        "sample_input": [],
        "sample_output": []
    }
    
    # Heuristic: The content is usually divided into divs with specific classes or by headers text.
    # Since we can't reliably parse nested divs with regex, we'll try to split by known section headers
    # or class names if they exist in the raw string.
    
    # 1. Try to find content by specific class markers which are consistent in HackerRank API
    # <div class='challenge_problem_statement_body'>...</div>
    # <div class='challenge_input_format_body'>...</div>
    
    sections_map = {
        "challenge_problem_statement_body": "description",
        "challenge_input_format_body": "input_format",
        "challenge_output_format_body": "output_format",
        "challenge_constraints_body": "constraints"
    }
    
    for cls, key in sections_map.items():
        # Regex to find the div body content. 
        # Note: This is fragile if div has attributes or spaces, but fits the specific API response observed.
        # We use non-greedy matches. 
        # We assume the content we want is inside <div class='...'> CONTENT </div>
        # But since nested divs exist, regex is tricky.
        # A safer regex approach for specific known structure:
        pattern = re.compile(f"class=['\"]{cls}['\"]>(.*?)</div>", re.DOTALL)
        match = pattern.search(html_content)
        if match:
            # We captured everything until the FIRST closing div. 
            # If the content contains nested divs (which it likely does), this regex will stop too early.
            # HOWEVER, for text extraction, we might just need to be smarter.
            
            # Alternative: Split the document by these class headers.
            pass

    # Better approach given the complex HTML: 
    # Use re to find start indices of known sections and extract text between them.
    
    current_key = "description" # Start with description (often the first block)
    
    # We will try to clean the WHOLE html first to text, but that loses structure.
    # Let's try to extract specific blocks based on the class names provided in the user's sample.
    
    def extract_section(cls_name):
        try:
            # Regex to find the start tag with the specific class, handling other classes and attributes
            # Matches <div ... class='... cls_name ...' ...>
            pattern = re.compile(f"<div[^>]*class=['\"][^'\"]*\\b{cls_name}\\b[^'\"]*['\"][^>]*>")
            match = pattern.search(html_content)
            
            if match:
                start_idx = match.end()
                # Now we need to find the matching closing div. 
                # Since we don't have a full DOM parser, we'll count divs.
                balance = 1
                curr = start_idx
                end_pos = -1
                
                while balance > 0 and curr < len(html_content):
                    next_open = html_content.find("<div", curr)
                    next_close = html_content.find("</div>", curr)
                    
                    if next_close == -1:
                        break # Malformed or truncated
                    
                    if next_open != -1 and next_open < next_close:
                        balance += 1
                        curr = next_open + 4
                    else:
                        balance -= 1
                        end_pos = next_close
                        curr = next_close + 6
                
                if balance == 0 and end_pos != -1:
                    raw_section = html_content[start_idx:end_pos]
                    return clean_html_content(raw_section)
        except:
            pass
        return ""

    structured_data["description"] = extract_section("challenge_problem_statement_body") or extract_section("challenge_question_body")
    structured_data["input_format"] = extract_section("challenge_input_format_body")
    structured_data["output_format"] = extract_section("challenge_output_format_body")
    structured_data["constraints"] = extract_section("challenge_constraints_body")
    
    # Samples are trickier as there can be multiple. 
    # challenge_sample_input_body, challenge_sample_output_body
    # We can iterate to find all occurrences.
    
    def extract_all_sections(cls_name):
        results = []
        search_start = 0
        pattern = re.compile(f"<div[^>]*class=['\"][^'\"]*\\b{cls_name}\\b[^'\"]*['\"][^>]*>")
        
        while True:
            match = pattern.search(html_content, search_start)
            if not match:
                break
            
            start_idx = match.end()
            balance = 1
            curr = start_idx
            end_pos = -1
            
            while balance > 0 and curr < len(html_content):
                next_open = html_content.find("<div", curr)
                next_close = html_content.find("</div>", curr)
                
                if next_close == -1: break
                
                if next_open != -1 and next_open < next_close:
                    balance += 1
                    curr = next_open + 4
                else:
                    balance -= 1
                    end_pos = next_close
                    curr = next_close + 6
            
            if end_pos != -1:
                raw = html_content[start_idx:end_pos]
                results.append(clean_html_content(raw))
                search_start = curr # Continue search after this block
            else:
                break
        return results

    structured_data["sample_input"] = extract_all_sections("challenge_sample_input_body")
    structured_data["sample_output"] = extract_all_sections("challenge_sample_output_body")
    
    # If description is empty, maybe fallback to cleaning the whole thing
    if not structured_data["description"] and not structured_data["input_format"]:
         structured_data["description"] = clean_html_content(html_content)

    return structured_data

def scrape_hackerrank_questions(
    track: str = "python", 
    subdomains: List[str] = [], # Now required logical input, though function default remains for safety
    status: Optional[List[str]] = None, 
    difficulty: Optional[List[str]] = None, 
    skills: Optional[List[str]] = None, 
    pages: int = 1
):
    """
    Scrapes HackerRank questions for a specific track using the internal REST API.
    Supports filtering by status, difficulty, subdomains, and skills.
    Parsing is done using standard libraries.
    """
    base_url = f"https://www.hackerrank.com/rest/contests/master/tracks/{track}/challenges"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    questions = []
    limit = 20 # Standard page size
    
    for page in range(pages):
        offset = page * limit
        print(f"[HackerRank] Scraping page {page + 1} (Offset: {offset}) for track '{track}'...")
        
        # Construct params manually to handle multiple filter values correctly
        params = [
            ("offset", str(offset)),
            ("limit", str(limit))
        ]
        
        # Apply filters
        # Note: subdomains are now critical as per user request
        if subdomains:
            for sub in subdomains:
                params.append(("filters[subdomains][]", sub))
        
        if status:
            for s in status:
                params.append(("filters[status][]", s))
        if difficulty:
            for d in difficulty:
                params.append(("filters[difficulty][]", d))
        if skills:
            for sk in skills:
                params.append(("filters[skills][]", sk))

        try:
            response = requests.get(base_url, headers=headers, params=params, timeout=10)
            
            if response.status_code != 200:
                print(f"[HackerRank] Error fetching list: {response.status_code} - {response.text[:200]}")
                break
                
            data = response.json()
            models = data.get("models", [])
            
            if not models:
                print(f"[HackerRank] No more questions found on page {page + 1}.")
                break
            
            print(f"[HackerRank] Found {len(models)} questions on page {page + 1}. Fetching details...")
            
            for item in models:
                slug = item.get("slug")
                if not slug:
                    continue
                    
                # Fetch full details
                detail_url = f"https://www.hackerrank.com/rest/contests/master/challenges/{slug}"
                try:
                    detail_response = requests.get(detail_url, headers=headers, timeout=10)
                    if detail_response.status_code == 200:
                        detail_data = detail_response.json()
                        model = detail_data.get("model", {})
                        
                        raw_html = model.get("body_html", "")
                        parsed_content = parse_hackerrank_description(raw_html)
                        
                        question_data = {
                            "title": model.get("name"),
                            "slug": slug,
                            "url": f"https://www.hackerrank.com/challenges/{slug}/problem",
                            "difficulty": model.get("difficulty_name"),
                            "score": model.get("max_score"),
                            "success_rate": model.get("success_ratio"),
                            "track": track,
                            "subdomain": item.get("track", {}).get("slug"), # sometimes provided
                            "platform": "HackerRank",
                            # Structured fields
                            "description": parsed_content.get("description", ""),
                            "input_format": parsed_content.get("input_format", ""),
                            "output_format": parsed_content.get("output_format", ""),
                            "constraints": parsed_content.get("constraints", ""),
                            "sample_input": parsed_content.get("sample_input", []),
                            "sample_output": parsed_content.get("sample_output", []),
                            # Keep raw HTML just in case
                            "description_html": raw_html
                        }
                        questions.append(question_data)
                    else:
                        print(f"[HackerRank] Failed to fetch details for {slug}")
                except Exception as e:
                    print(f"[HackerRank] Error fetching detail for {slug}: {e}")
                    
        except Exception as e:
            print(f"[HackerRank] Error scraping page {page + 1}: {e}")
            break
            
    print(f"[HackerRank] Scraped total {len(questions)} questions.")
    return questions
