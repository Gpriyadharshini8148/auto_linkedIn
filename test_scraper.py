import requests
from bs4 import BeautifulSoup
import json
import urllib.parse

def test_scrape():
    keywords = "Python Backend Developer"
    location = "Bangalore"
    # f_E=1,2 represents Internship (1) and Entry-level (2)
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords={urllib.parse.quote(keywords)}&location={urllib.parse.quote(location)}&f_E=1,2&start=0"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/"
    }
    
    print(f"Requesting URL: {url}")
    response = requests.get(url, headers=headers, timeout=10)
    print(f"Status Code: {response.status_code}")
    
    if response.status_code != 200:
        print("Failed to fetch jobs page.")
        print(response.text[:500])
        return

    soup = BeautifulSoup(response.text, 'html.parser')
    # seeMoreJobPostings returns a list of <li> elements directly
    job_cards = soup.find_all('li')
    if not job_cards:
        # Sometimes it might return job-search-card div or other elements directly
        job_cards = soup.select('.job-search-card') or soup.select('.base-card')
        
    print(f"Found {len(job_cards)} job cards raw elements.")
    
    jobs = []
    for card in job_cards:
        # Title
        title_el = card.find(class_="base-search-card__title") or card.select_one('.base-search-card__title')
        title = title_el.get_text(strip=True) if title_el else None
        
        # Company
        company_el = card.find(class_="base-search-card__subtitle") or card.select_one('.base-search-card__subtitle')
        company = company_el.get_text(strip=True) if company_el else None
        
        # Location
        location_el = card.find(class_="job-search-card__location") or card.select_one('.job-search-card__location')
        loc = location_el.get_text(strip=True) if location_el else None
        
        # Job Link & Job ID
        link_el = card.find('a', class_="base-card__full-link") or card.select_one('a[href*="/jobs/view/"]')
        link = link_el.get('href') if link_el else None
        if not link:
            # Try any link in the card
            link_el = card.find('a')
            if link_el:
                link = link_el.get('href')
                
        # Clean link (remove tracking parameters)
        if link:
            parsed_link = urllib.parse.urlparse(link)
            # Reconstruct URL without query params (or at least without tracking info)
            link = f"{parsed_link.scheme}://{parsed_link.netloc}{parsed_link.path}"
        
        # Date Posted
        date_el = card.find('time')
        date_posted = date_el.get_text(strip=True) if date_el else None
        if not date_posted:
            date_el = card.find(class_="job-search-card__listdate") or card.find(class_="job-search-card__listdate--new")
            date_posted = date_el.get_text(strip=True) if date_el else None

        # Extract Job ID
        job_id = None
        if link:
            # Link is usually like: https://in.linkedin.com/jobs/view/python-developer-at-company-12345678
            # or https://www.linkedin.com/jobs/view/12345678
            parts = parsed_link.path.strip('/').split('/')
            if parts:
                last_part = parts[-1]
                # If last part is a number or contains number at the end
                import re
                match = re.search(r'(\d+)$', last_part)
                if match:
                    job_id = match.group(1)
        
        if title:
            jobs.append({
                "job_id": job_id,
                "title": title,
                "company": company,
                "location": loc,
                "link": link,
                "date_posted": date_posted
            })
            
    print(f"Successfully parsed {len(jobs)} jobs.")
    print(json.dumps(jobs[:3], indent=2))

if __name__ == "__main__":
    test_scrape()
