"""
ExpertiniCmScraper
------------------
Scrapes IT / tech job listings from cm.expertini.com.

NOTE on 403s: expertini uses Cloudflare bot protection. The scraper tries
multiple URL variants and longer delays. If all fail, the portal is skipped
gracefully — emploi.cm's 149 jobs are sufficient for the analysis pipeline.
"""

import logging
import time
import random

from typing import Optional

from config.settings import MAX_PAGES_PER_SITE, PORTALS
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "expertini_cm"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]

SEARCH_URL_VARIANTS = [
    "https://cm.expertini.com/jobs/search/it-jobs-cameroon/",
    "https://cm.expertini.com/jobs/search/informatique-jobs-cameroon/",
    "https://cm.expertini.com/jobs/search/developer-jobs-cameroon/",
    "https://cm.expertini.com/jobs/search/software-jobs-cameroon/",
    "https://expertini.com/jobs/cameroon/technology-jobs/",
]


class ExpertiniCmScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)

    def scrape(self) -> list[dict]:
        working_url = self._resolve_url()
        if working_url is None:
            logger.warning(
                f"[{PORTAL_KEY}] All URL variants returned 403 (Cloudflare bot protection). "
                f"Skipping this portal — data from emploi.cm is sufficient for analysis."
            )
            return []

        logger.info(f"[{PORTAL_KEY}] Working URL found: {working_url}")
        jobs = []

        for page in range(1, MAX_PAGES_PER_SITE + 1):
            url = f"{working_url}?page={page}" if page > 1 else working_url
            logger.info(f"[{PORTAL_KEY}] Scraping page {page} -> {url}")

            soup = self.get_rotating(url, retries=3)
            if soup is None:
                break

            listing_urls = self._parse_listing_page(soup)
            if not listing_urls:
                logger.info(f"[{PORTAL_KEY}] No listings on page {page} - stopping.")
                break

            for listing_url in listing_urls:
                job = self._parse_detail_page(listing_url)
                if job:
                    jobs.append(job)

            logger.info(f"[{PORTAL_KEY}] Page {page}: {len(listing_urls)} listings found.")
            time.sleep(random.uniform(4, 8))

        logger.info(f"[{PORTAL_KEY}] Total scraped: {len(jobs)}")
        return jobs

    def _resolve_url(self) -> Optional[str]:
        for url in SEARCH_URL_VARIANTS:
            logger.info(f"[{PORTAL_KEY}] Trying: {url}")
            time.sleep(random.uniform(5, 10))
            soup = self.get_rotating(url, retries=2)
            if soup is not None:
                return url
            logger.info(f"[{PORTAL_KEY}] Blocked at: {url}")
        return None

    def _parse_listing_page(self, soup) -> list[str]:
        urls = []
        links = (
            soup.select("article a[href*='/job']")
            or soup.select("div[class*='job'] a[href]")
            or soup.select("h2 a[href]")
            or soup.select("h3 a[href]")
            or soup.select("a[href*='/jobs/']")
        )
        for a_tag in links:
            href = a_tag.get("href", "")
            if not href:
                continue
            full_url = href if href.startswith("http") else BASE_URL + href
            if full_url not in urls and full_url != BASE_URL:
                urls.append(full_url)
        return urls

    def _parse_detail_page(self, url: str) -> Optional[dict]:
        soup = self.get_rotating(url, retries=2)
        if soup is None:
            return None

        title_tag = soup.select_one("h1") or soup.select_one("[class*='title']")
        title = self.clean(title_tag.get_text()) if title_tag else ""

        company_tag = soup.select_one("[class*='company']") or soup.select_one("[class*='employer']")
        company = self.clean(company_tag.get_text()) if company_tag else ""

        city_tag = soup.select_one("[class*='location']") or soup.select_one("[class*='city']")
        city = self.clean(city_tag.get_text()) if city_tag else ""

        desc_tag = (
            soup.select_one("div[class*='description']")
            or soup.select_one("div[class*='content']")
            or soup.select_one("section[class*='job']")
        )
        description = self.clean(desc_tag.get_text()) if desc_tag else ""

        date_tag = soup.select_one("time") or soup.select_one("[class*='date']")
        date_posted = self.clean(date_tag.get_text()) if date_tag else ""

        exp_tag = soup.select_one("[class*='experience']")
        experience = self.clean(exp_tag.get_text()) if exp_tag else ""

        return self.make_job(
            title=title, company=company, city=city, experience=experience,
            skills_raw="", description=description, url=url, date_posted=date_posted,
        )
