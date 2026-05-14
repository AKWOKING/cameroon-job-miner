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

No compression issues — talent.com serves clean UTF-8, no Cloudflare zstd.
"""

import logging
from typing import List, Optional

from config.settings import MAX_PAGES_PER_SITE, PORTALS
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "talent_cm"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]


class TalentCmScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)

    # ── Entry point ────────────────────────────────────────────────────────────

    def scrape(self) -> List[dict]:
        jobs = []

        for page in range(1, MAX_PAGES_PER_SITE + 1):
            url = SEARCH_URL if page == 1 else f"{SEARCH_URL}&p={page}"
            logger.info(f"[{PORTAL_KEY}] Scraping page {page} -> {url}")

            soup = self.get(url)
            if soup is None:
                logger.warning(f"[{PORTAL_KEY}] No response on page {page} — stopping.")
                break

            listing_urls = self._parse_listing_page(soup)
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

    # ── Parse listing page — collect detail page URLs ──────────────────────────

    def _parse_listing_page(self, soup) -> List[str]:
        """
        Each job on the listing page is an <h2> containing an <a href="/view?id=...">
        We collect those hrefs and build absolute URLs.
        """
        urls = []

        # Primary: <h2> tags containing job title links
        for h2 in soup.select("h2"):
            a = h2.select_one("a[href]")
            if not a:
                continue
            href = a.get("href", "")
            if not href or "/view" not in href:
                continue
            full_url = href if href.startswith("http") else BASE_URL + href
            if full_url not in urls:
                urls.append(full_url)

        # Fallback: any card link pointing to /view
        if not urls:
            for a in soup.select("a[href*='/view?id=']"):
                href = a.get("href", "")
                full_url = href if href.startswith("http") else BASE_URL + href
                if full_url not in urls:
                    urls.append(full_url)

        return urls

    # ── Parse detail page ──────────────────────────────────────────────────────

    def _parse_detail_page(self, url: str) -> Optional[dict]:
        soup = self.get(url)
        if soup is None:
            return None

        # ── Title — always in <h1> ─────────────────────────────────────────────
        h1 = soup.select_one("h1")
        title = self.clean(h1.get_text()) if h1 else ""

        # ── Company & city — appear together near the top ──────────────────────
        # talent.com renders: "COMPANY • City" in a subtitle element
        company, city = self._extract_company_city(soup)

        # ── Description — full job text ────────────────────────────────────────
        # Skills will be extracted from this in Phase 2 by the NLP pipeline
        desc_tag = (
            soup.select_one("div.description")
            or soup.select_one("[class*='description']")
            or soup.select_one("div[class*='content']")
            or soup.select_one("main")
        )
        description = self.clean(desc_tag.get_text()) if desc_tag else ""

        # ── Date posted ────────────────────────────────────────────────────────
        date_tag = (
            soup.select_one("time")
            or soup.select_one("[class*='date']")
            or soup.select_one("[datetime]")
        )
        if date_tag:
            date_posted = date_tag.get("datetime") or self.clean(date_tag.get_text())
        else:
            # talent.com sometimes shows "Il y a X jours" in plain text
            date_posted = self._extract_date_text(soup)

        if not title:
            logger.debug(f"[{PORTAL_KEY}] Skipping page with no title: {url}")
            return None

        return self.make_job(
            title=title,
            company=company,
            city=city,
            description=description,
            skills_raw="",   # extracted by NLP in Phase 2
            url=url,
            date_posted=date_posted,
        )

    # ── Field helpers ──────────────────────────────────────────────────────────

    def _extract_company_city(self, soup) -> tuple:
        """
        talent.com shows company and city near the title.
        Confirmed pattern from fetch: "SEGA • Cameroon" or "Company • City"
        Tries several selectors; falls back to splitting on the bullet separator.
        """
        # Try structured selectors first
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

        # Last resort: look for the bullet separator anywhere in the page header
        header = soup.select_one("header") or soup.select_one("[class*='job-header']")
        if header:
            text = self.clean(header.get_text())
            if "\u2022" in text:
                parts = text.split("\u2022")
                return self.clean(parts[0]), self.clean(parts[1]) if len(parts) > 1 else ""

        return "", ""

    def _extract_date_text(self, soup) -> str:
        """
        talent.com shows relative dates like 'Il y a plus de 30 jours'.
        Find that text anywhere on the page.
        """
        for phrase in ["Il y a", "il y a", "days ago", "Posted"]:
            tag = soup.find(string=lambda s: s and phrase in s)
            if tag:
                return self.clean(str(tag))
        return ""
