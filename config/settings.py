"""
Central configuration for the Cameroon Job Market Miner.
Edit values here — no other file needs to change.
"""

import os
from pathlib import Path

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent.parent
DATA_DIR    = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH     = DATA_DIR / "jobs.db"
EXPORTS_DIR = DATA_DIR / "exports"

# ── Scraper behaviour ──────────────────────────────────────────────────────────
REQUEST_DELAY_MIN = 2   # seconds — minimum pause between requests (be polite)
REQUEST_DELAY_MAX = 5   # seconds — maximum pause
MAX_PAGES_PER_SITE = 10 # safety cap — increase once you've verified pagination

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "fr-CM,fr;q=0.9,en;q=0.8",
    # Only advertise gzip/deflate — do NOT include br or zstd.
    # emploi.cm is behind Cloudflare which serves zstd when br/zstd
    # are in Accept-Encoding. Neither httpx nor requests can decode
    # zstd. Omitting them forces Cloudflare to fall back to gzip.
    "Accept-Encoding": "gzip, deflate",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

# Rotating user-agent pool — used by scrapers that hit 403 (e.g. expertini_cm).
# BaseScraper.get_rotating() picks one at random each request.
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.3; rv:123.0) Gecko/20100101 Firefox/123.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]

REQUEST_TIMEOUT = 15  # seconds

# ── Portal URLs ────────────────────────────────────────────────────────────────
PORTALS = {
    "emploi_cm": {
        "name": "Emploi.cm",
        "base_url": "https://www.emploi.cm",
        "search_url": "https://www.emploi.cm/recherche-jobs-cameroun/informatique",
        "enabled": True,
    },
    "talent_cm": {
        "name": "Talent.cm",
        "base_url": "https://cm.talent.com",
        "search_url": "https://cm.talent.com/jobs?k=informatique&l=Cameroon",
        "enabled": True,
    },
    "expertini_cm": {
        "name": "Expertini.cm",
        "base_url": "https://cm.expertini.com",
        "search_url": "https://cm.expertini.com/jobs/search/it-jobs-cameroon/",
        "enabled": True,
    },
    "workconnect": {
        "name": "WorkConnect",
        "base_url": "https://www.workconnectjob.com",
        "search_url": "https://www.workconnectjob.com/jobs",
        "enabled": True,
    },
    "newjobscm": {
        "name": "NewJobs Cameroon",
        "base_url": "https://newjobscameroon.com",
        "search_url": "https://newjobscameroon.com/jobs/",
        "enabled": True,
    },
}

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_LEVEL = "INFO"   # DEBUG | INFO | WARNING | ERROR
