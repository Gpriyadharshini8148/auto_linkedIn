// Application State
let jobsList = [];
let lastSyncedTime = null;
let currentLocationFilter = 'all';
let currentSearchQuery = '';

// DOM Elements
const jobsGrid = document.getElementById('jobs-grid');
const searchInput = document.getElementById('search-input');
const filterChips = document.querySelectorAll('.chip');
const btnRefresh = document.getElementById('btn-refresh');
const toastContainer = document.getElementById('toast-container');
const jobsCountEl = document.getElementById('jobs-count');

// Calendar Filter Elements
const startDateInput = document.getElementById('start-date');
const endDateInput = document.getElementById('end-date');
const btnResetDates = document.getElementById('btn-reset-dates');

// Stats Elements
const statTotal = document.getElementById('stat-total');
const statBangalore = document.getElementById('stat-bangalore');
const statChennai = document.getElementById('stat-chennai');
const statLastUpdate = document.getElementById('stat-last-update');

// Initialize Dashboard
document.addEventListener('DOMContentLoaded', () => {
    // Initial fetch
    fetchJobs();
    
    // Bind Search Input
    searchInput.addEventListener('input', debounce((e) => {
        currentSearchQuery = e.target.value.trim().toLowerCase();
        renderFilteredJobs();
    }, 250));
    
    // Bind Location Filters (Chips)
    filterChips.forEach(chip => {
        chip.addEventListener('click', () => {
            filterChips.forEach(c => c.classList.remove('active'));
            chip.classList.add('active');
            currentLocationFilter = chip.getAttribute('data-location');
            renderFilteredJobs();
        });
    });
    
    // Bind Calendar Date Filters
    startDateInput.addEventListener('change', () => renderFilteredJobs());
    endDateInput.addEventListener('change', () => renderFilteredJobs());
    
    // Bind Reset Date Button
    btnResetDates.addEventListener('click', () => {
        startDateInput.value = '';
        endDateInput.value = '';
        renderFilteredJobs();
    });
    
    // Bind Refresh button
    btnRefresh.addEventListener('click', triggerUpdate);
});

// Debounce helper to improve search performance
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Fetch jobs from SQLite Backend API or static JSON file
async function fetchJobs() {
    showLoading();
    try {
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        const url = isLocal ? '/api/jobs' : 'jobs.json';
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success !== undefined) {
            // Local backend API response: { success, last_synced, jobs }
            if (data.success) {
                jobsList = data.jobs || [];
                lastSyncedTime = data.last_synced || null; // use backend-provided sync time
                updateStats();
                renderFilteredJobs();
            } else {
                showEmptyState(data.message || "Failed to load listings");
                showToast("error", "Error loading jobs: " + data.message);
            }
        } else if (data.last_synced !== undefined) {
            // Static jobs.json (new format): { last_synced, jobs }
            jobsList = data.jobs || [];
            lastSyncedTime = data.last_synced;
            updateStats();
            renderFilteredJobs();
        } else {
            // Static jobs.json (legacy format): plain array
            jobsList = Array.isArray(data) ? data : [];
            lastSyncedTime = null;
            updateStats();
            renderFilteredJobs();
        }
    } catch (error) {
        const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
        if (isLocal) {
            showEmptyState("Could not connect to the backend server. Make sure app.py is running.");
            showToast("error", "Network error. Failed to load listings.");
        } else {
            showEmptyState("No job listings database found. Run local updates first.");
            showToast("error", "Static jobs.json file not found.");
        }
    }
}

// Calculate approximate calendar date from relative date strings (e.g. "2 days ago")
function parseRelativeDate(dateStr, scrapedAtStr) {
    if (!dateStr) return null;
    
    const baseDate = scrapedAtStr ? new Date(scrapedAtStr) : new Date();
    const str = dateStr.trim().toLowerCase();
    
    if (str.includes("just now") || str.includes("today") || str.includes("now") || str.includes("hour")) {
        return baseDate;
    }
    if (str.includes("yesterday")) {
        const d = new Date(baseDate);
        d.setDate(d.getDate() - 1);
        return d;
    }
    
    const match = str.match(/(\d+)\s*(day|week|month|year)s?\s*ago/);
    if (match) {
        const val = parseInt(match[1], 10);
        const unit = match[2];
        const d = new Date(baseDate);
        
        if (unit === "day") {
            d.setDate(d.getDate() - val);
        } else if (unit === "week") {
            d.setDate(d.getDate() - (val * 7));
        } else if (unit === "month") {
            d.setMonth(d.getMonth() - val);
        } else if (unit === "year") {
            d.setFullYear(d.getFullYear() - val);
        }
        return d;
    }
    
    const parsed = new Date(dateStr);
    if (!isNaN(parsed.getTime())) return parsed;
    
    return baseDate;
}

// Render dynamic job cards
function renderFilteredJobs() {
    const startDateVal = startDateInput.value;
    const endDateVal = endDateInput.value;

    // Filter jobsList locally based on search query, location chip, and date filters
    const filtered = jobsList.filter(job => {
        const matchesLocation = currentLocationFilter === 'all' || 
                               job.search_location.toLowerCase() === currentLocationFilter.toLowerCase();
                               
        const matchesSearch = !currentSearchQuery || 
                             job.title.toLowerCase().includes(currentSearchQuery) || 
                             job.company.toLowerCase().includes(currentSearchQuery) ||
                             job.location.toLowerCase().includes(currentSearchQuery);
                             
        // Filter by LinkedIn Job Posted date range
        let matchesDate = true;
        if (startDateVal || endDateVal) {
            const postedDate = parseRelativeDate(job.date_posted, job.scraped_at);
            if (postedDate) {
                if (startDateVal) {
                    const startLimit = new Date(startDateVal + 'T00:00:00');
                    if (postedDate < startLimit) matchesDate = false;
                }
                if (endDateVal) {
                    const endLimit = new Date(endDateVal + 'T23:59:59');
                    if (postedDate > endLimit) matchesDate = false;
                }
            } else {
                matchesDate = false;
            }
        }
                             
        return matchesLocation && matchesSearch && matchesDate;
    });
    
    // Update count
    jobsCountEl.textContent = filtered.length;
    
    if (filtered.length === 0) {
        showEmptyState("No job postings match your filters.");
        return;
    }
    
    jobsGrid.innerHTML = '';
    
    filtered.forEach(job => {
        const card = document.createElement('div');
        card.className = 'job-card';
        
        // Format location and date
        const relativeTime = job.date_posted || 'Recently';
        const displayLocation = job.location || job.search_location;
        const jobUrl = job.link || '#';
        
        card.innerHTML = `
            <div class="card-header">
                <a href="${jobUrl}" target="_blank" class="job-title" title="Open Job Listing">${escapeHTML(job.title)}</a>
                <span class="company-name">${escapeHTML(job.company || 'Unknown Company')}</span>
            </div>
            <div class="card-body">
                <span class="tag tag-location">
                    <i data-lucide="map-pin"></i>
                    ${escapeHTML(displayLocation)}
                </span>
                <span class="tag tag-experience">
                    <i data-lucide="award"></i>
                    Fresher
                </span>
                <span class="tag tag-time">
                    <i data-lucide="clock"></i>
                    ${escapeHTML(relativeTime)}
                </span>
            </div>
            <div class="card-footer">
                <span class="date-text">Sync: ${formatScrapedDate(job.scraped_at)}</span>
                <a href="${jobUrl}" target="_blank" class="btn-apply">
                    <span>Apply</span>
                    <i data-lucide="external-link"></i>
                </a>
            </div>
        `;
        
        jobsGrid.appendChild(card);
    });
    
    // Re-initialize Lucide icons for injected HTML
    lucide.createIcons();
}

// Update Header Statistics
function updateStats() {
    statTotal.textContent = jobsList.length;
    
    const blrCount = jobsList.filter(j => j.search_location.toLowerCase() === 'bangalore').length;
    const maaCount = jobsList.filter(j => j.search_location.toLowerCase() === 'chennai').length;
    
    statBangalore.textContent = blrCount;
    statChennai.textContent = maaCount;
    
    // Use the top-level last_synced timestamp if available (most accurate)
    // Otherwise fall back to the max scraped_at across all jobs
    if (lastSyncedTime) {
        // last_synced is stored in UTC — convert to local time for display
        const syncDate = new Date(lastSyncedTime + ' UTC');
        statLastUpdate.textContent = syncDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            + ' ' + syncDate.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } else if (jobsList.length > 0) {
        const dates = jobsList.map(j => new Date(j.scraped_at));
        const maxDate = new Date(Math.max.apply(null, dates));
        statLastUpdate.textContent = maxDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
            + ' ' + maxDate.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } else {
        statLastUpdate.textContent = '-';
    }
}

// Trigger background scraper and load results
async function triggerUpdate() {
    const isLocal = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
    if (!isLocal) {
        showToast("info", "✅ Jobs are auto-synced daily via GitHub Actions at 9:00 AM IST. Check back tomorrow for fresh listings!");
        return;
    }
    
    if (btnRefresh.classList.contains('loading')) return;
    
    btnRefresh.classList.add('loading');
    btnRefresh.disabled = true;
    btnRefresh.querySelector('span').textContent = 'Scraping LinkedIn...';
    showToast("info", "Starting scraper in background. This will take 10-15 seconds.");
    
    try {
        const response = await fetch('/api/update', { method: 'POST' });
        const data = await response.json();
        
        if (data.success) {
            showToast("success", "Sync Complete! " + data.message);
            // Fetch updated listings
            await fetchJobs();
        } else {
            showToast("error", "Update failed: " + data.message);
        }
    } catch (error) {
        showToast("error", "Network error. Failed to trigger updates.");
    } finally {
        btnRefresh.classList.remove('loading');
        btnRefresh.disabled = false;
        btnRefresh.querySelector('span').textContent = 'Refresh Listings';
    }
}

// Toast Notifications Helper
function showToast(type, message) {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const iconName = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-triangle' : 'info';
    
    toast.innerHTML = `
        <i data-lucide="${iconName}"></i>
        <span>${escapeHTML(message)}</span>
    `;
    
    toastContainer.appendChild(toast);
    lucide.createIcons();
    
    // Slide out and remove after 4.5 seconds
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        setTimeout(() => toast.remove(), 300);
    }, 4500);
}

// States Renders Helper
function showLoading() {
    jobsGrid.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Fetching active job postings from SQLite database...</p>
        </div>
    `;
}

function showEmptyState(msg) {
    jobsGrid.innerHTML = `
        <div class="empty-state">
            <i data-lucide="help-circle"></i>
            <h3>No Job Openings</h3>
            <p>${escapeHTML(msg)}</p>
        </div>
    `;
    lucide.createIcons();
}

function escapeHTML(str) {
    if (!str) return '';
    return str.replace(/[&<>'"]/g, 
        tag => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;' }[tag] || tag)
    );
}

function formatScrapedDate(dateStr) {
    if (!dateStr) return 'N/A';
    try {
        const date = new Date(dateStr);
        return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    } catch (e) {
        return dateStr;
    }
}
