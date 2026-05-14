"""
ExpertiniCmScraper
------------------
Scrapes IT / tech job listings from cm.expertini.com.

Expertini uses paginated listing pages. Each job card links to a detail page
that contains the full description. We scrape both layers.
Pagination: URL pattern /jobs/search/it-jobs-cameroon/?page=N
"""

import logging

from typing import Optional

from config.settings import MAX_PAGES_PER_SITE, PORTALS
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "expertini_cm"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]


class ExpertiniCmScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)

    # ── Entry point ────────────────────────────────────────────────────────────

    def scrape(self) -> list[dict]:
        jobs = []
        for page in range(1, MAX_PAGES_PER_SITE + 1):
            url = f"{SEARCH_URL}?page={page}" if page > 1 else SEARCH_URL
            logger.info(f"[{PORTAL_KEY}] Scraping page {page} → {url}")

            soup = self.get(url)
            if soup is None:
                break

            listing_urls = self._parse_listing_page(soup)
            if not listing_urls:
                logger.info(f"[{PORTAL_KEY}] No listings on page {page} — stopping.")
                break

            for listing_url in listing_urls:
                job = self._parse_detail_page(listing_url)
                if job:
                    jobs.append(job)

            logger.info(f"[{PORTAL_KEY}] Page {page}: {len(listing_urls)} listings found.")

        logger.info(f"[{PORTAL_KEY}] Total scraped: {len(jobs)}")
        return jobs

    # ── Parse listing page ─────────────────────────────────────────────────────

    def _parse_listing_page(self, soup) -> list[str]:
        """Return absolute URLs of individual job detail pages."""
        urls = []

        # Expertini wraps each job in an <article> or a div with class "job"
        links = (
            soup.select("article a[href*='/job']")
            or soup.select("div[class*='job'] a[href]")
            or soup.select("h2 a[href]")
        )

        for a_tag in links:
            href = a_tag.get("href", "")
            if not href:
                continue
            full_url = href if href.startswith("http") else BASE_URL + href
            if full_url not in urls:
                urls.append(full_url)

        return urls

    # ── Parse detail page ──────────────────────────────────────────────────────

    def _parse_detail_page(self, url: str) -> Optional[dict]:
        soup = self.get(url)
        if soup is None:
            return None

        # Title
        title_tag = soup.select_one("h1") or soup.select_one("[class*='title']")
        title = self.clean(title_tag.get_text()) if title_tag else ""

        # Company
        company_tag = (
            soup.select_one("[class*='company']")
            or soup.select_one("[class*='employer']")
        )
        company = self.clean(company_tag.get_text()) if company_tag else ""

        # City
        city_tag = (
            soup.select_one("[class*='location']")
            or soup.select_one("[class*='city']")
            or soup.select_one("[class*='address']")
        )
        city = self.clean(city_tag.get_text()) if city_tag else ""

        # Description (full text — skills extracted later by NLP pipeline)
        desc_tag = (
            soup.select_one("div[class*='description']")
            or soup.select_one("div[class*='content']")
            or soup.select_one("section[class*='job']")
        )
        description = self.clean(desc_tag.get_text()) if desc_tag else ""

        # Date
        date_tag = soup.select_one("time") or soup.select_one("[class*='date']")
        date_posted = self.clean(date_tag.get_text()) if date_tag else ""

        # Experience
        exp_tag = soup.select_one("[class*='experience']")
        experience = self.clean(exp_tag.get_text()) if exp_tag else ""

        return self.make_job(
            title=title,
            company=company,
            city=city,
            experience=experience,
            skills_raw="",   # will be extracted in Phase 2 NLP pipeline
            description=description,
            url=url,
            date_posted=date_posted,
        )
