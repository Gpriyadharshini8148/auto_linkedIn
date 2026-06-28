# LinkedIn Job Search MCP Server

An MCP (Model Context Protocol) server built using Python and FastMCP to search and scrape public job openings on LinkedIn without requiring user authentication.

## Features

- **Search Public Job Listings**: Retrieves job titles, company names, locations, date posted, and direct links.
- **Pre-configured Defaults**: Optimised for finding "Python Backend Developer" jobs for freshers (internships and entry-level roles) in Bangalore and Chennai.
- **Experience Filtering**: Filters by internship, entry_level, associate, mid_senior, director, and executive.
- **Multiple Locations**: Can search across multiple locations simultaneously and aggregates the results.

## Requirements

Ensure you have Python 3.10+ installed and on your system path.

To install dependencies:
```bash
pip install -r requirements.txt
```

## Running the Server

### Development / CLI Testing Mode
FastMCP has a built-in development CLI. You can run the server in dev mode to test tools, view schemas, or call tools directly from a terminal:

```bash
fastmcp dev server.py
```
This will start the MCP inspector. You can open the provided local URL in your browser to test the tool.

### Production Run Mode
To run the server in standard stdio mode:
```bash
python server.py
```

### Web Dashboard Mode (Interactive UI)
To run the interactive web application dashboard:
```bash
python app.py
```
Then open [http://localhost:8000](http://localhost:8000) in your web browser. This launches a visual dashboard where you can filter, search, and update listings in real-time.


## MCP Client Configuration

To register this server with an MCP client (such as Claude Desktop), edit your configuration file:

- **Claude Desktop Configuration Path**: `%APPDATA%\Claude\claude_desktop_config.json`

Add the following config:

```json
{
  "mcpServers": {
    "linkedin-jobs": {
      "command": "python",
      "args": [
        "d:/linked in mcp/server.py"
      ],
      "env": {}
    }
  }
}
```

> **Note**: Update the path `"d:/linked in mcp/server.py"` to the absolute path of the `server.py` file on your machine if you move this folder. Use forward slashes `/` in the path to avoid JSON escaping issues.

## Available Tools

### `search_linkedin_jobs`
Search for job postings on LinkedIn.

**Parameters**:
- `keywords` (string, default: `"Python Backend Developer"`): The job search keywords.
- `locations` (list of strings, default: `["Bangalore", "Chennai"]`): Locations to search.
- `experience_levels` (list of strings, default: `["internship", "entry_level"]`): Experience filters. Allowed values: `internship`, `entry_level`, `associate`, `mid_senior`, `director`, `executive`.
- `limit_per_location` (integer, default: `15`): Maximum number of jobs to fetch per location.

**Return Value**:
A JSON string containing the list of jobs found, with elements:
- `job_id`: The LinkedIn Job ID.
- `title`: The job title.
- `company`: The company name.
- `location`: The location of the job.
- `link`: Direct link to the job application.
- `date_posted`: Relative time posted.
- `search_location`: The location queried for this job.

### `query_stored_jobs`
Query previously scraped job listings stored in the local SQLite database.

**Parameters**:
- `search_location` (string, optional): Filter by location searched (e.g. "Bangalore", "Chennai").
- `keyword_filter` (string, optional): Substring filter for job title or company name.
- `limit` (integer, default: `50`): Maximum number of records to return.

**Return Value**:
A JSON string containing the list of matching jobs found in the local database.

## Daily Auto-Updates (Windows Task Scheduler)

A daily update script `update_jobs.py` is included to automatically scrape job listings every morning and save them to a local SQLite database (`jobs.db`) while eliminating duplicate listings.

### Manual Update
To fetch and merge new job listings manually:
```bash
python update_jobs.py
```
This updates/creates the `jobs.db` file in the same directory. (If a legacy `jobs.json` file is found, it will automatically migrate the listings to the database on the first run).

### Auto-Update Schedule (Windows Task Scheduler)
You can schedule the update script to run automatically every morning using PowerShell:

1. Open PowerShell and run:
   ```powershell
   $action = New-ScheduledTaskAction -Execute "C:\Program Files\Python312\python.exe" -Argument "d:\linked in mcp\update_jobs.py"
   $trigger = New-ScheduledTaskTrigger -Daily -At 11:00AM
   Register-ScheduledTask -TaskName "LinkedInJobUpdater" -Action $action -Trigger $trigger -Description "Daily LinkedIn Job Updater for Python Backend Developer Freshers" -Force
   ```

2. To verify the task has been scheduled successfully, run:
   ```powershell
   Get-ScheduledTask -TaskName "LinkedInJobUpdater"
   ```

3. To delete or stop the scheduled updater in the future, run:
   ```powershell
   Unregister-ScheduledTask -TaskName "LinkedInJobUpdater" -Confirm:$false
   ```

## Live Deployment on Netlify (Static Hosting)

The dashboard is configured with a fallback mechanism that allows it to run as a static website on **Netlify** using a pre-scraped static database `jobs.json`.

### How it works:
1. **Local Mode**: When accessed on `localhost`, the website talks to `app.py` and reads live from `jobs.db` SQLite (and allows triggering updates from the button).
2. **Netlify Mode**: When deployed online, it automatically falls back to reading the pre-built static file `jobs.json` (and disables the direct scrape button since there's no backend python server online).

### Deployment Steps:

1. **Build the latest data locally**:
   Run the update script to scrape the latest jobs and generate the static `jobs.json` file:
   ```bash
   python update_jobs.py
   ```

2. **Upload to Netlify (Drag and Drop)**:
   - Go to [Netlify Drop](https://app.netlify.com/drop).
   - Drag and drop your workspace folder (`d:/linked in mcp`) or select the files:
     - `index.html`
     - `style.css`
     - `client.js`
     - `jobs.json`
   - Netlify will compile and give you a public URL instantly!

3. **Deploy with Git (Recommended for updates)**:
   - Push your workspace files (`index.html`, `style.css`, `client.js`, and `jobs.json`) to a GitHub repository.
   - Import the repository in [Netlify Dashboard](https://app.netlify.com) for automatic deployments.
   - When you run local updates and push the new `jobs.json` to GitHub, Netlify will automatically redeploy the site with the fresh listings!



