import json
import os
import sqlite3
from server import search_linkedin_jobs

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")

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
            INSERT OR IGNORE INTO jobs (job_id, title, company, location, link, date_posted, search_location)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            job.get("title"),
            job.get("company"),
            job.get("location"),
            job.get("link"),
            job.get("date_posted"),
            job.get("search_location")
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
    exclude_keywords = [
        "senior", "sr", "sse", "lead", "principal", "manager", "architect", 
        "staff", "director", "head", "mid", "experienced", "intern",
        "founding", "ii", "iii", "iv", "expert", "specialist", "consultant"
    ]
    
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT job_id, title FROM jobs")
    rows = cursor.fetchall()
    
    deleted_count = 0
    for job_id, title in rows:
        title_lower = title.lower()
        words = re.findall(r'\b\w+\b', title_lower)
        is_fresher = True
        for word in exclude_keywords:
            if word in words:
                is_fresher = False
                break
                
        if is_fresher:
            if re.search(r'\b([2-9]|\d{2,})\+?\s*(?:year|yr)s?\b', title_lower):
                is_fresher = False
            elif re.search(r'\b([2-9]|\d{2,})\s*-\s*\d+\s*(?:year|yr)s?\b', title_lower):
                is_fresher = False
                
        if not is_fresher:
            cursor.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            deleted_count += 1
            
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
    
    # Check if there is a legacy jobs.json to migrate
    json_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.json")
    if os.path.exists(json_file):
        print(f"Found legacy {json_file}. Migrating to SQLite...")
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                legacy_jobs = json.load(f)
            new_added, total = save_jobs_to_db(legacy_jobs)
            print(f"Migrated {new_added} jobs to SQLite database.")
            os.replace(json_file, json_file + ".bak")
            print("Renamed jobs.json to jobs.json.bak")
        except Exception as e:
            print(f"Error during legacy migration: {e}")
            
    # Search with default parameters (Python Backend Developer, Bangalore & Chennai, internship & entry_level)
    # We set a limit of 25 jobs per location.
    try:
        result_str = search_linkedin_jobs(limit_per_location=25)
        result = json.loads(result_str)
    except Exception as e:
        print(f"Error executing scraper: {e}")
        return
    
    if not result.get("success"):
        print("Scraping failed.")
        return
        
    new_jobs = result.get("jobs", [])
    print(f"Scraped {len(new_jobs)} jobs.")
    
    try:
        new_added, total = save_jobs_to_db(new_jobs)
        print(f"Saved to DB: {new_added} new jobs added. Total jobs in DB: {total}")
        
        # If new jobs are successfully added, auto-push static jobs.json to GitHub
        if new_added > 0:
            git_push_changes()
        else:
            # We can still push to ensure sync if we want, or skip. Let's push to keep it updated.
            # But skipping keeps GitHub build minutes clean if nothing changes.
            pass
    except Exception as e:
        print(f"Error saving jobs to database: {e}")

if __name__ == "__main__":
    main()
