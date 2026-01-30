import time
import re
from playwright.sync_api import sync_playwright

def clean_text(text):
    if not text:
        return ""
    # Remove multiple newlines and extra spaces
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def scrape_exercism_questions(language: str, pages: int = 1):
    """
    Scrapes Exercism exercises for a specific language track.
    """
    scraped_data = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )
        page = context.new_page()

        # Exercism usually scrolls for more exercises, but the user requested 'pages'.
        # On Exercism, the list is often long or paginated if status=available is used.
        # Let's check the URL structure.
        base_url = f"https://exercism.org/tracks/{language}/exercises?status=available"
        print(f"[Exercism List] Fetching list from: {base_url}")
        
        try:
            page.goto(base_url, wait_until="networkidle", timeout=60000)
            
            # Since Exercism might use lazy loading, we scroll a bit if pages > 1
            if pages > 1:
                for _ in range(pages * 2):
                    page.evaluate("window.scrollBy(0, 800)")
                    time.sleep(0.5)

            # Find columns/cards
            cards = page.query_selector_all('a.c-exercise-widget')
            print(f"[Exercism List] Found {len(cards)} exercises on the list page.")

            for card in cards:
                href = card.get_attribute('href')
                if not href:
                    continue
                
                # Construct full URL
                full_url = f"https://exercism.org{href}"
                
                # Avoid duplicates in the list
                if any(item['url'] == full_url for item in scraped_data):
                    continue

                slug = href.split('/')[-1]
                
                title_el = card.query_selector('.--title')
                title = title_el.inner_text().strip() if title_el else slug.replace('-', ' ').title()
                
                difficulty_el = card.query_selector('.c-difficulty-tag') or card.query_selector('.--data')
                difficulty = difficulty_el.inner_text().strip() if difficulty_el else "Unknown"
                
                blurb_el = card.query_selector('.--blurb')
                blurb = blurb_el.inner_text().strip() if blurb_el else ""

                scraped_data.append({
                    "title": title,
                    "url": full_url,
                    "slug": slug,
                    "difficulty": difficulty,
                    "blurb": blurb,
                    "platform": "Exercism",
                    "language": language
                })
        except Exception as e:
            print(f"[Exercism List] Error fetching list: {e}")

        print(f"[Exercism List] Starting detailed scrape for {len(scraped_data)} items...")

        # Detail Scraping
        for item in scraped_data:
            try:
                print(f"[Exercism Detail] Scraping: {item['title']}")
                detail_page = context.new_page()
                detail_page.goto(item["url"], wait_until="domcontentloaded", timeout=60000)
                
                # Wait for core instructions
                try:
                    detail_page.wait_for_selector('section.instructions', timeout=15000)
                except:
                    print(f"[Exercism Detail] Timeout waiting for instructions on {item['title']}")
                
                # Extract content
                content_el = detail_page.query_selector('section.instructions')
                description = ""
                if content_el:
                    # Get the textual content specifically if possible
                    textual = content_el.query_selector('.c-textual-content')
                    if textual:
                        description = textual.inner_text().strip()
                    else:
                        description = content_el.inner_text().strip()
                
                item["description"] = description
                
                detail_page.close()
                time.sleep(1) # Be gentle
            except Exception as e:
                print(f"[Exercism Detail] Error on {item['title']}: {e}")
                try:
                    detail_page.close()
                except:
                    pass

        browser.close()
    
    return scraped_data
