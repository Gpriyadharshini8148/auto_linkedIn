import time
import requests
from bs4 import BeautifulSoup
import urllib.parse
import re
import logging
from typing import List, Dict, Any
from fastmcp import FastMCP

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("linkedin_mcp")

# Initialize MCP server
mcp = FastMCP("LinkedInJobSearch")

EXP_MAP = {
    "internship": "1",
    "entry_level": "2",
    "associate": "3",
    "mid_senior": "4",
    "director": "5",
    "executive": "6"
}

def is_fresher_title(title: str) -> bool:
    """
    Checks if a job title is suitable for a fresher by excluding senior and non-fresher keywords.
    """
    title_lower = title.lower()
    exclude_keywords = [
        "senior", "sr", "sse", "lead", "principal", "manager", "architect", 
        "staff", "director", "head", "mid", "experienced", "intern",
        "founding", "ii", "iii", "iv", "expert", "specialist", "consultant"
    ]
    # Check for exact word matches using regex
    words = re.findall(r'\b\w+\b', title_lower)
    for word in exclude_keywords:
        if word in words:
            return False
            
    # Check for experience indicators representing 2+ years (e.g. 3 years, 2+ yrs, 2-5 yrs)
    if re.search(r'\b([2-9]|\d{2,})\+?\s*(?:year|yr)s?\b', title_lower):
        return False
    if re.search(r'\b([2-9]|\d{2,})\s*-\s*\d+\s*(?:year|yr)s?\b', title_lower):
        return False
        
    return True

def is_fresher_description(job_id: str, headers: Dict[str, str]) -> bool:
    """
    Fetches the job description using the LinkedIn seeMoreJobPostings detail endpoint
    and verifies if it matches any experienced years requirements.
    """
    if not job_id:
        return True
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
    try:
        # Sleep for 1 second to avoid hitting rate limits
        time.sleep(1.0)
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, "html.parser")
            desc_div = soup.find(class_="show-more-less-html__markup")
            if desc_div:
                desc_text = desc_div.get_text(separator=" ", strip=True).lower()
                
                # Check for 2+ years of experience regex patterns
                if re.search(r'\b([2-9]|\d{2,})\+?\s*(?:year|yr)s?\b', desc_text):
                    logger.info(f"Skipping job ID {job_id} because description matches experienced years limit.")
                    return False
                if re.search(r'\b([2-9]|\d{2,})\s*(?:-|to)\s*\d+\s*(?:year|yr)s?\b', desc_text):
                    logger.info(f"Skipping job ID {job_id} because description matches experienced years range.")
                    return False
    except Exception as e:
        logger.error(f"Error fetching description for job {job_id}: {e}")
    return True

def scrape_jobs_for_location(
    keywords: str,
    location: str,
    experience_codes: str,
    limit: int
) -> List[Dict[str, Any]]:
    """
    Scrapes job postings for a single location using the LinkedIn guest seeMoreJobPostings API.
    """
    jobs = []
    start = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://www.google.com/"
    }

    # LinkedIn seeMoreJobPostings usually loads 10 to 25 items per request.
    # We loop to paginate using the 'start' parameter until we reach the limit.
    while len(jobs) < limit:
        # Construct the guest job search endpoint
        params = {
            "keywords": keywords,
            "location": location,
            "start": start
        }
        if experience_codes:
            params["f_E"] = experience_codes
            
        url_params = urllib.parse.urlencode(params)
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{url_params}"
        
        logger.info(f"Fetching jobs from URL: {url}")
        
        try:
            response = requests.get(url, headers=headers, timeout=15)
            if response.status_code != 200:
                logger.error(f"Error fetching jobs: Status code {response.status_code}")
                break
                
            soup = BeautifulSoup(response.text, 'html.parser')
            job_cards = soup.find_all('li')
            if not job_cards:
                job_cards = soup.select('.job-search-card') or soup.select('.base-card')
                
            if not job_cards:
                logger.info("No more job cards found.")
                break
                
            new_jobs_added = 0
            for card in job_cards:
                if len(jobs) >= limit:
                    break
                    
                # Title
                title_el = card.find(class_="base-search-card__title") or card.select_one('.base-search-card__title')
                title = title_el.get_text(strip=True) if title_el else None
                
                # Exclude non-fresher titles
                if title and not is_fresher_title(title):
                    logger.info(f"Skipping non-fresher job title: {title}")
                    continue
                
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
                    link_el = card.find('a')
                    if link_el:
                        link = link_el.get('href')
                        
                # Clean link (remove tracking parameters)
                if link:
                    parsed_link = urllib.parse.urlparse(link)
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
                    parts = parsed_link.path.strip('/').split('/')
                    if parts:
                        last_part = parts[-1]
                        match = re.search(r'(\d+)$', last_part)
                        if match:
                            job_id = match.group(1)
                
                # Inspect job description for experience years limits
                if job_id and not is_fresher_description(job_id, headers):
                    logger.info(f"Skipping job: {title} at {company} (ID: {job_id}) due to experience requirements in description.")
                    continue
                
                if title:
                    jobs.append({
                        "job_id": job_id,
                        "title": title,
                        "company": company,
                        "location": loc,
                        "link": link,
                        "date_posted": date_posted,
                        "search_location": location
                    })
                    new_jobs_added += 1
            
            if new_jobs_added == 0:
                # No new jobs parsed from the page, stop pagination loop to avoid infinite loop
                break
                
            # Increment start by the number of job cards found on this page
            start += len(job_cards)
            
            # Rate limiting delay
            time.sleep(1.5)
            
        except Exception as e:
            logger.error(f"Request failed: {str(e)}")
            break
            
    return jobs

@mcp.tool()
def search_linkedin_jobs(
    keywords: str = "Python Backend Developer",
    locations: List[str] = ["Bangalore", "Chennai"],
    experience_levels: List[str] = ["entry_level"],
    limit_per_location: int = 15
) -> str:
    """
    Search for job postings on LinkedIn based on keywords, locations, and experience levels.
    
    Args:
        keywords (str): The search terms (e.g. "Python Backend Developer").
        locations (List[str]): List of locations to search (e.g. ["Bangalore", "Chennai"]).
        experience_levels (List[str]): List of experience levels. 
            Allowed values: "internship", "entry_level", "associate", "mid_senior", "director", "executive".
        limit_per_location (int): Maximum number of job postings to fetch per location.
        
    Returns:
        str: A JSON string containing the list of jobs found.
    """
    # Map experience levels to LinkedIn codes
    exp_codes_list = []
    for level in experience_levels:
        level_clean = level.lower().strip().replace(" ", "_")
        if level_clean in EXP_MAP:
            exp_codes_list.append(EXP_MAP[level_clean])
    
    exp_codes = ",".join(exp_codes_list) if exp_codes_list else None
    
    all_jobs = []
    for location in locations:
        logger.info(f"Searching jobs in location: {location}")
        jobs = scrape_jobs_for_location(
            keywords=keywords,
            location=location,
            experience_codes=exp_codes,
            limit=limit_per_location
        )
        all_jobs.extend(jobs)
        # Sleep between different locations to avoid rate limits
        if len(locations) > 1:
            time.sleep(2)
            
    result = {
        "success": True,
        "count": len(all_jobs),
        "jobs": all_jobs
    }
    
    import json
    return json.dumps(result, indent=2)

@mcp.tool()
def query_stored_jobs(
    search_location: str = None,
    keyword_filter: str = None,
    limit: int = 50
) -> str:
    """
    Query previously scraped job listings stored in the local SQLite database.
    
    Args:
        search_location (str, optional): Filter by location searched (e.g. "Bangalore", "Chennai").
        keyword_filter (str, optional): Substring filter for job title or company name.
        limit (int): Maximum number of records to return.
        
    Returns:
        str: A JSON string containing matching job records.
    """
    import sqlite3
    import json
    import os
    
    db_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")
    if not os.path.exists(db_file):
        return json.dumps({"success": False, "message": "Database file not found. Run the update script first."})
        
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    query = "SELECT job_id, title, company, location, link, date_posted, search_location, scraped_at FROM jobs WHERE 1=1"
    params = []
    
    if search_location:
        query += " AND search_location LIKE ?"
        params.append(f"%{search_location}%")
        
    if keyword_filter:
        query += " AND (title LIKE ? OR company LIKE ?)"
        params.append(f"%{keyword_filter}%")
        params.append(f"%{keyword_filter}%")
        
    query += " ORDER BY scraped_at DESC LIMIT ?"
    params.append(limit)
    
    try:
        cursor.execute(query, params)
        rows = cursor.fetchall()
        jobs = [dict(row) for row in rows]
        conn.close()
        return json.dumps({"success": True, "count": len(jobs), "jobs": jobs}, indent=2)
    except Exception as e:
        conn.close()
        return json.dumps({"success": False, "message": f"Database query failed: {str(e)}"})

if __name__ == "__main__":
    mcp.run()
