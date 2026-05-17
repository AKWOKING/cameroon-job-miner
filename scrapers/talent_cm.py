"""
TalentCmScraper
---------------
Scrapes tech/IT job listings from cm.talent.com.

Confirmed structure (fetched April 2026):
  Search URL : https://cm.talent.com/jobs?k=informatique&l=Cameroon
  Pagination  : &p=2, &p=3 ... (1-indexed, no param needed for page 1)
  Listing page: each job is an <h2><a href="/view?id=XXXXXXXX"> inside a card
  Detail page : <h1> title, company + location in a subtitle line,
                full description in <div class="description"> paragraphs
                No pre-tagged skills — NLP pipeline handles extraction (Phase 2)

DNS note: cm.talent.com occasionally fails DNS resolution from some regions.
The scraper automatically falls back to alternative search URLs.
"""

import logging
from typing import List, Optional

from config.settings import MAX_PAGES_PER_SITE, PORTALS
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "talent_cm"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]

# Fallback search URLs tried in order if the primary fails DNS
FALLBACK_URLS = [
    "https://cm.talent.com/jobs?k=informatique&l=Cameroon",
    "https://cm.talent.com/jobs?k=tech&l=Cameroon",
    "https://www.talent.com/jobs?k=informatique&l=Cameroon",        # www variant
    "https://www.talent.com/jobs?k=developer&l=Cameroon&radius=100",
]


class TalentCmScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)

    # ── Entry point ────────────────────────────────────────────────────────────

    def scrape(self) -> List[dict]:
        jobs = []

        # Resolve which base search URL actually works
        working_url = self._resolve_search_url()
        if working_url is None:
            logger.warning(
                f"[{PORTAL_KEY}] All search URLs failed (DNS or network issue). "
                f"This portal will be skipped. Try again with a VPN or different network."
            )
            return []

        logger.info(f"[{PORTAL_KEY}] Using search URL: {working_url}")
        # Determine base for relative link construction
        base = "https://cm.talent.com" if "cm.talent.com" in working_url else "https://www.talent.com"

        for page in range(1, MAX_PAGES_PER_SITE + 1):
            url = working_url if page == 1 else f"{working_url}&p={page}"
            logger.info(f"[{PORTAL_KEY}] Scraping page {page} -> {url}")

            soup = self.get_rotating(url)
            if soup is None:
                logger.warning(f"[{PORTAL_KEY}] No response on page {page} — stopping.")
                break

            listing_urls = self._parse_listing_page(soup, base)
            if not listing_urls:
                logger.info(f"[{PORTAL_KEY}] No listings on page {page} — stopping.")
                break

            logger.info(f"[{PORTAL_KEY}] Page {page}: {len(listing_urls)} listings found.")

            for detail_url in listing_urls:
                job = self._parse_detail_page(detail_url)
                if job:
                    jobs.append(job)

            logger.info(f"[{PORTAL_KEY}] Running total: {len(jobs)}")

        logger.info(f"[{PORTAL_KEY}] Finished. Total scraped: {len(jobs)}")
        return jobs

    def _resolve_search_url(self) -> Optional[str]:
        """Try each search URL in order, return the first one that responds."""
        for url in FALLBACK_URLS:
            logger.info(f"[{PORTAL_KEY}] Testing URL: {url}")
            soup = self.get_rotating(url, retries=2)
            if soup is not None:
                return url
        return None

    # ── Parse listing page — collect detail page URLs ──────────────────────────

    def _parse_listing_page(self, soup, base: str) -> List[str]:
        urls = []

        for h2 in soup.select("h2"):
            a = h2.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            if not href or "/view" not in href:
                continue
            full_url = href if href.startswith("http") else base + href
            if full_url not in urls:
                urls.append(full_url)

        if not urls:
            for a in soup.select("a[href*='/view?id=']"):
                href = a.get("href", "")
                full_url = href if href.startswith("http") else base + href
                if full_url not in urls:
                    urls.append(full_url)

        return urls

    # ── Parse detail page ──────────────────────────────────────────────────────

    def _parse_detail_page(self, url: str) -> Optional[dict]:
        soup = self.get_rotating(url, retries=2)
        if soup is None:
            return None

        h1 = soup.select_one("h1")
        title = self.clean(h1.get_text()) if h1 else ""

        company, city = self._extract_company_city(soup)

        desc_tag = (
            soup.select_one("div.description")
            or soup.select_one("[class*='description']")
            or soup.select_one("div[class*='content']")
            or soup.select_one("main")
        )
        description = self.clean(desc_tag.get_text()) if desc_tag else ""

        date_tag = (
            soup.select_one("time")
            or soup.select_one("[class*='date']")
            or soup.select_one("[datetime]")
        )
        if date_tag:
            date_posted = date_tag.get("datetime") or self.clean(date_tag.get_text())
        else:
            date_posted = self._extract_date_text(soup)

        if not title:
            logger.debug(f"[{PORTAL_KEY}] Skipping page with no title: {url}")
            return None

        return self.make_job(
            title=title,
            company=company,
            city=city,
            description=description,
            skills_raw="",
            url=url,
            date_posted=date_posted,
        )

    # ── Field helpers ──────────────────────────────────────────────────────────

    def _extract_company_city(self, soup) -> tuple:
        selectors = [
            "[class*='company']",
            "[class*='employer']",
            "[class*='subtitle']",
            "[class*='header'] p",
        ]
        for sel in selectors:
            tag = soup.select_one(sel)
            if tag:
                text = self.clean(tag.get_text())
                if "\u2022" in text or " • " in text:
                    parts = text.split("\u2022")
                    company = self.clean(parts[0]) if len(parts) > 0 else text
                    city    = self.clean(parts[1]) if len(parts) > 1 else ""
                    return company, city
                if text:
                    return text, ""

        header = soup.select_one("header") or soup.select_one("[class*='job-header']")
        if header:
            text = self.clean(header.get_text())
            if "\u2022" in text:
                parts = text.split("\u2022")
                return self.clean(parts[0]), self.clean(parts[1]) if len(parts) > 1 else ""

        return "", ""

    def _extract_date_text(self, soup) -> str:
        for phrase in ["Il y a", "il y a", "days ago", "Posted"]:
            tag = soup.find(string=lambda s: s and phrase in s)
            if tag:
                return self.clean(str(tag))
        return ""

