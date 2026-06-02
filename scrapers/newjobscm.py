"""
NewJobsCmScraper
----------------
Scrapes job listings from newjobscameroon.com using WP Job Board.

The site structure:
- Job listings are in <table id="wpjb-job-list"> with <tbody class="wpjb-job-list">
- Each job is a <tr> with classes like wpjb-free wpjb-type-full-time wpjb-category-{category}
- Columns:
  - wpjb-column-logo: company logo (placeholder div)
  - wpjb-column-title: job title (<a href>) and company (<small class="wpjb-sub">)
  - wpjb-column-location: location icon + text + job type (<small>)
  - wpjb-column-date wpjb-last: date posted (format: "Aug, 30<br />")

Pagination: Uses WordPress standard /page/N/ format (e.g., /page/2/, /page/3/)
"""

import logging
from typing import List, Optional

from config.settings import MAX_PAGES_PER_SITE, PORTALS
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "newjobscm"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]


class NewJobsCmScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)

    def scrape(self) -> List[dict]:
        jobs = []

        # WordPress standard pagination: /page/N/
        for page in range(1, MAX_PAGES_PER_SITE + 1):
            # Page 1 is the base URL, subsequent pages use /page/N/
            url = SEARCH_URL if page == 1 else f"https://newjobscameroon.com/page/{page}/"
            logger.info(f"[{PORTAL_KEY}] Scraping page {page} -> {url}")

            soup = self.get(url)
            if soup is None:
                logger.warning(f"[{PORTAL_KEY}] No response on page {page} — stopping.")
                break

            # Save debug HTML for first page
            if page == 1:
                self._dump_html(soup)

            page_jobs = self._parse_job_listings(soup)
            if not page_jobs:
                logger.info(f"[{PORTAL_KEY}] No jobs found on page {page} — stopping.")
                break

            jobs.extend(page_jobs)
            logger.info(
                f"[{PORTAL_KEY}] Page {page}: {len(page_jobs)} jobs. "
                f"Running total: {len(jobs)}"
            )

        logger.info(f"[{PORTAL_KEY}] Finished. Total scraped: {len(jobs)}")
        return jobs

    def _dump_html(self, soup):
        """Save raw HTML for debugging purposes."""
        from config.settings import DATA_DIR
        from pathlib import Path

        debug_path = Path(DATA_DIR) / "debug_newjobscm.html"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(soup.prettify(), encoding="utf-8")
        logger.info(f"[{PORTAL_KEY}] Raw HTML saved -> {debug_path}")

    def _parse_job_listings(self, soup) -> List[dict]:
        """Parse all job listings from the job table."""
        jobs = []

        # Find the job table body
        tbody = soup.select_one("tbody.wpjb-job-list")
        if not tbody:
            logger.warning(f"[{PORTAL_KEY}] Could not find job list table body")
            return jobs

        # Find all job rows
        job_rows = tbody.select("tr")
        logger.debug(f"[{PORTAL_KEY}] Found {len(job_rows)} job rows")

        for row in job_rows:
            job = self._parse_job_row(row)
            if job:
                jobs.append(job)

        return jobs

    def _parse_job_row(self, row) -> Optional[dict]:
        """Parse a single job row from the table."""
        try:
            # Extract columns
            cols = row.select("td")
            if len(cols) < 4:
                logger.debug(f"[{PORTAL_KEY}] Row has insufficient columns: {len(cols)}")
                return None

            # Column 0: Logo (skip)
            # Column 1: Title and Company
            title_col = cols[1]
            title_tag = title_col.select_one("a")
            company_tag = title_col.select_one("small.wpjb-sub")

            title = self._clean_text(title_tag.get_text()) if title_tag else ""
            company = self._clean_text(company_tag.get_text()) if company_tag else ""

            # Column 2: Location and Job Type
            location_col = cols[2]
            location_text = self._clean_text(location_col.get_text())
            # Extract location (before job type info)
            location_parts = location_text.split()
            # Find where job type starts (Full-time, Part-time, etc.)
            location = ""
            job_type_indicators = ["Full-time", "Part-time", "Contract", "Temporary", "Internship"]
            for i, part in enumerate(location_parts):
                if part in job_type_indicators or (i > 0 and location_parts[i-1] in job_type_indicators):
                    break
                location += part + " "
            location = location.strip()
            # Clean up trailing commas
            location = location.rstrip(',').strip()

            # Column 3: Date Posted
            date_col = cols[3] if len(cols) > 3 else None
            date_posted = ""
            if date_col:
                # Get text and clean up <br> tags
                date_text = date_col.get_text()
                # Replace <br> with space and clean
                date_posted = self._clean_text(date_text.replace("<br>", " ").replace("<br/>", " "))

            # Extract URL from title link
            url = ""
            if title_tag and title_tag.has_attr('href'):
                url = title_tag['href']
                if not url.startswith('http'):
                    url = BASE_URL + url

            # Basic validation
            if not title:
                logger.debug(f"[{PORTAL_KEY}] Skipping row with empty title")
                return None

            return self.make_job(
                title=title,
                company=company,
                city=location,
                experience="",  # Not clearly available in listing
                skills_raw="",  # Not clearly available in listing
                description="",  # Would need detail page visit
                url=url,
                date_posted=date_posted,
            )

        except Exception as e:
            logger.warning(f"[{PORTAL_KEY}] Error parsing job row: {e}")
            return None

    def _clean_text(self, text: Optional[str]) -> str:
        """Clean and normalize text."""
        if not text:
            return ""
        # Remove extra whitespace and normalize
        return " ".join(text.split())