import http.server
import json
import urllib.parse
import sqlite3
import os
import subprocess

PORT = 8000
DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jobs.db")

class JobDashboardRequestHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == "/api/jobs":
            self.handle_api_jobs(parsed_url)
        else:
            # Fallback to SimpleHTTPRequestHandler to serve index.html, style.css, client.js
            super().do_GET()
            
    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == "/api/update":
            self.handle_api_update()
        else:
            self.send_error(404, "File not found")
            
    def handle_api_jobs(self, parsed_url):
        query_params = urllib.parse.parse_qs(parsed_url.query)
        location = query_params.get("location", [None])[0]
        q = query_params.get("q", [None])[0]
        
        if not os.path.exists(DB_FILE):
            self.send_response_json({"success": False, "message": "Database not found"}, status=404)
            return
            
        try:
            conn = sqlite3.connect(DB_FILE)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            sql_query = "SELECT job_id, title, company, location, link, date_posted, search_location, scraped_at FROM jobs WHERE 1=1"
            params = []
            
            if location and location.lower() != "all":
                sql_query += " AND search_location LIKE ?"
                params.append(f"%{location}%")
                
            if q:
                sql_query += " AND (title LIKE ? OR company LIKE ?)"
                params.append(f"%{q}%")
                params.append(f"%{q}%")
                
            sql_query += " ORDER BY scraped_at DESC"
            
            cursor.execute(sql_query, params)
            rows = cursor.fetchall()
            jobs = [dict(row) for row in rows]
            
            # Fetch the latest sync time from the entire jobs table
            cursor.execute("SELECT MAX(scraped_at) FROM jobs")
            last_synced_row = cursor.fetchone()
            last_synced = last_synced_row[0] if last_synced_row else None
            conn.close()
            
            self.send_response_json({"success": True, "count": len(jobs), "last_synced": last_synced, "jobs": jobs})
        except Exception as e:
            self.send_response_json({"success": False, "message": str(e)}, status=500)
            
    def handle_api_update(self):
        try:
            # Run the python update script and capture output
            script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "update_jobs.py")
            process = subprocess.run(["python", script_path], capture_output=True, text=True)
            
            if process.returncode == 0:
                conn = sqlite3.connect(DB_FILE)
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM jobs")
                total = cursor.fetchone()[0]
                conn.close()
                self.send_response_json({
                    "success": True, 
                    "message": "Jobs database successfully updated!", 
                    "total_jobs": total,
                    "output": process.stdout
                })
            else:
                self.send_response_json({
                    "success": False, 
                    "message": "Update script failed.", 
                    "error": process.stderr
                }, status=500)
        except Exception as e:
            self.send_response_json({"success": False, "message": str(e)}, status=500)
            
    def send_response_json(self, data, status=200):
        response_content = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")  # Allow CORS
        self.send_header("Content-Length", len(response_content))
        self.end_headers()
        self.wfile.write(response_content)

def run():
    # Make sure we run in the directory of the script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    server_address = ("", PORT)
    httpd = http.server.HTTPServer(server_address, JobDashboardRequestHandler)
    print(f"Starting server on http://localhost:{PORT}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server.")
        httpd.server_close()

if __name__ == "__main__":
    run()
