from app.geeksforgeeks import scrape_gfg_questions
import json

def test():
    print("Starting GFG test for company: Infosys")
    # Using an empty search query to focus only on the company filter
    query = ""
    company = "Infosys"
    pages = 1
    
    results = scrape_gfg_questions(query, pages, company)
    
    print(f"Scraped {len(results)} questions for company {company}.")
    
    if results:
        with open("gfg_infosys_test.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=4)
        print("Results saved to gfg_infosys_test.json")
        
        # Verify if 'company' field is present and correct
        all_have_company = all(r.get("company") == company for r in results)
        print(f"All items have correct company field? {all_have_company}")
    else:
        print("No results found.")

if __name__ == "__main__":
    test()
