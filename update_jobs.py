import json
import os
import sqlite3
import time
from server import search_linkedin_jobs

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")

SEARCH_KEYWORDS = [
    "Python Backend Developer",
    "Backend Developer Python",
    "Python Developer",
    "Senior Python Developer",
    "Junior Python Developer",
    "Python Software Engineer",
    "Backend Software Engineer Python",
    "Python Engineer",
    "Django Developer",
    "Django Backend Developer",
    "Flask Developer",
    "Flask Backend Developer",
    "FastAPI Developer",
    "FastAPI Backend Developer",
    "Python API Developer",
    "REST API Developer Python",
    "Python Microservices Developer",
    "Backend Engineer Microservices",
    "Python AWS Developer",
    "Python Cloud Engineer",
    "Python Kubernetes Developer",
    "Python DevOps Developer",
    "Entry Level Python Developer",
    "Associate Software Engineer Python",
    "Graduate Python Developer",
    "Trainee Python Developer"
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            title TEXT,
            company TEXT,
            location TEXT,
            link TEXT,
            date_posted TEXT,
            search_location TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Add description_checked column if not exists
    try:
        cursor.execute("ALTER TABLE jobs ADD COLUMN description_checked INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn

def save_jobs_to_db(jobs):
    conn = init_db()
    cursor = conn.cursor()
    new_count = 0
    
    for job in jobs:
        job_id = job.get("job_id")
        if not job_id:
            # Generate a hash-based key if job_id is missing to ensure uniqueness
            import hashlib
            key_source = f"{job.get('title')}-{job.get('company')}"
            job_id = hashlib.md5(key_source.encode('utf-8')).hexdigest()
            
        cursor.execute("""
            INSERT OR IGNORE INTO jobs (job_id, title, company, location, link, date_posted, search_location, description_checked)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("link"),
            job.get("date_posted"),
            job.get("search_location"),
            job.get("description_checked", 1)
        ))
        
        if cursor.rowcount > 0:
            new_count += 1
            
    conn.commit()
    
    # Query all jobs to export to jobs.json for static site deployment (Netlify)
    cursor.execute("SELECT job_id, title, company, location, link, date_posted, search_location, scraped_at FROM jobs ORDER BY scraped_at DESC")
    rows = cursor.fetchall()
    all_jobs = [
        {
            "job_id": r[0],
            "title": r[1],
            "company": r[2],
            "location": r[3],
            "link": r[4],
            "date_posted": r[5],
            "search_location": r[6],
            "scraped_at": r[7]
        }
        for r in rows
    ]
    
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
    try:
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(all_jobs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"Error exporting static JSON file: {e}")
        
    # Get total count
    cursor.execute("SELECT COUNT(*) FROM jobs")
    total_count = cursor.fetchone()[0]
    conn.close()
    
    return new_count, total_count

def cleanup_non_fresher_jobs():
    import re
    import requests
    from bs4 import BeautifulSoup
    import time
    
    exclude_keywords = [
        "senior", "sr", "sse", "lead", "principal", "manager", "architect", 
        "staff", "director", "head", "mid", "experienced", "intern",
        "founding", "ii", "iii", "iv", "expert", "specialist", "consultant"
    ]
    
    conn = init_db()
    cursor = conn.cursor()
    
    # 1. Clean up jobs that fail basic title filters immediately
    cursor.execute("SELECT job_id, title FROM jobs")
    rows = cursor.fetchall()
    
    deleted_count = 0
    for job_id, title in rows:
        title_lower = title.lower()
        words = re.findall(r'\b\w+\b', title_lower)
        is_candidate = True
        for word in exclude_keywords:
            if word in words:
                is_candidate = False
                break
        if is_candidate:
            if re.search(r'\b([2-9]|\d{2,})\+?\s*(?:year|yr)s?\b', title_lower) or re.search(r'\b([2-9]|\d{2,})\s*-\s*\d+\s*(?:year|yr)s?\b', title_lower):
                is_candidate = False
                
        if not is_candidate:
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            deleted_count += 1
            
    conn.commit()
    
    # 2. Deep scan descriptions for remaining unchecked candidates
    cursor.execute("SELECT job_id, title, company FROM jobs WHERE description_checked = 0")
    unchecked_candidates = cursor.fetchall()
    
    if unchecked_candidates:
        print(f"Deep scanning {len(unchecked_candidates)} job descriptions for experience requirements...")
        
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    for job_id, title, company in unchecked_candidates:
        url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"
        is_fresher_desc = True
        try:
            time.sleep(1.0) # sleep 1s to prevent rate limits
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, "html.parser")
                desc_div = soup.find(class_="show-more-less-html__markup")
                if desc_div:
                    desc_text = desc_div.get_text(separator=" ", strip=True).lower()
                    
                    # Regex check for 2+ years of experience
                    if re.search(r'\b([2-9]|\d{2,})\+?\s*(?:year|yr)s?\b', desc_text) or re.search(r'\b([2-9]|\d{2,})\s*(?:-|to)\s*\d+\s*(?:year|yr)s?\b', desc_text):
                        is_fresher_desc = False
            elif response.status_code == 404:
                # Job posting is gone, we can delete it or mark it checked. Let's delete it.
                cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
                deleted_count += 1
                continue
        except Exception as e:
            # Leave description_checked as 0 to retry next time
            continue
            
        if not is_fresher_desc:
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            deleted_count += 1
            print(f"Purged from DB (requires experience in description): '{title}' at '{company}'")
        else:
            cursor.execute("UPDATE jobs SET description_checked = 1 WHERE job_id = ?", (job_id,))
            
    conn.commit()
    conn.close()
    
    if deleted_count > 0:
        print(f"Cleaned up database: removed {deleted_count} non-fresher jobs.")

def git_push_changes():
    import subprocess
    print("Auto-syncing to GitHub repository...")
    try:
        # Check if git is initialized in the script directory
        script_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.exists(os.path.join(script_dir, ".git")):
            print("Git repository not initialized. Run git init to link with GitHub.")
            return
            
        # Add changes
        subprocess.run(["git", "add", "jobs.json"], cwd=script_dir, check=True)
        # Commit changes
        res = subprocess.run(["git", "commit", "-m", "sync latest job listings [skip ci]"], cwd=script_dir, capture_output=True, text=True)
        if "nothing to commit" in res.stdout or "nothing added to commit" in res.stdout or "no changes added to commit" in res.stdout:
            print("No new changes to commit. Skipping push.")
            return
            
        # Push changes
        subprocess.run(["git", "push"], cwd=script_dir, check=True)
        print("Successfully pushed latest jobs to GitHub! Netlify redeployment triggered.")
    except Exception as e:
        print(f"Failed to auto-push to GitHub: {e}")

def main():
    print("Starting daily LinkedIn job updates with SQLite...")
    
    # Clean up any existing non-fresher jobs
    cleanup_non_fresher_jobs()
    
    # Legacy migration block removed as migration is complete.
            
    # Loop through all keywords to search LinkedIn
    all_scraped_jobs = []
    print(f"Scraping LinkedIn for {len(SEARCH_KEYWORDS)} different search terms...")
    
    for idx, keyword in enumerate(SEARCH_KEYWORDS, 1):
        print(f"[{idx}/{len(SEARCH_KEYWORDS)}] Searching for: '{keyword}'...")
        try:
            # Fetch up to 5 jobs per location to keep runs fast, diverse, and rate-limit safe
            result_str = search_linkedin_jobs(keywords=keyword, limit_per_location=5)
            result = json.loads(result_str)
            if result.get("success"):
                scraped_jobs = result.get("jobs", [])
                all_scraped_jobs.extend(scraped_jobs)
                print(f"  -> Found {len(scraped_jobs)} potential fresher jobs.")
            else:
                print(f"  -> Scraping failed for '{keyword}': {result.get('message')}")
        except Exception as e:
            print(f"  -> Error executing scraper for '{keyword}': {e}")
            
        time.sleep(1.0)
        
    print(f"Total potential fresher jobs scraped: {len(all_scraped_jobs)}")
    
    try:
        new_added, total = save_jobs_to_db(all_scraped_jobs)
        print(f"Saved to DB: {new_added} new jobs added. Total jobs in DB: {total}")
        
        # If new jobs are successfully added, auto-push static jobs.json to GitHub
        if new_added > 0:
            git_push_changes()
    except Exception as e:
        print(f"Error saving jobs to database: {e}")

if __name__ == "__main__":
    main()
