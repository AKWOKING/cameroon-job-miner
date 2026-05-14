"""
EmploiCmScraper
---------------
Confirmed HTML structure (emploi.cm, April 2026):

  <div class="card card-job featured" data-href="/offre-emploi-cameroun/...">
    <div class="card-job-detail">
      <h3><a href="/offre-emploi-cameroun/...">Title</a></h3>
      <a class="card-job-company company-name" href="...">Company</a>
      <div class="card-job-description"><p>...</p></div>
      <ul>
        <li>Niveau d´études requis : <strong>Bac+3...</strong></li>
        <li>Niveau d'expérience : <strong>Expérience entre 2 ans...</strong></li>
        <li>Contrat proposé : <strong>CDI & CDD</strong></li>
        <li>Région de : <strong>Douala & Yaoundé</strong></li>
        <li>Compétences clés : <strong>API - BACK END - DOCKER - GIT...</strong></li>
      </ul>
      <time datetime="2026-04-19">19.04.2026</time>
    </div>
  </div>

Key insight: the outer wrapper is div.card.card-job (two classes).
The URL is in data-href on THAT outer div, not on card-job-detail.
All structured fields are in <li> tags — we read the <strong> child.
"""

import logging
from pathlib import Path
from typing import List, Optional

from config.settings import DATA_DIR, MAX_PAGES_PER_SITE, PORTALS
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "emploi_cm"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;"
        "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "fr-CM,fr;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "same-origin",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class EmploiCmScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)
        self.update_headers(BROWSER_HEADERS)
        self._warmed_up = False

    # ── Session warmup ─────────────────────────────────────────────────────────

    def _warmup(self):
        if self._warmed_up:
            return
        logger.info(f"[{PORTAL_KEY}] Warming up session on homepage...")
        self.update_headers({"Referer": BASE_URL + "/"})
        self.get(BASE_URL)
        self.update_headers({"Referer": SEARCH_URL})
        self._warmed_up = True

    # ── Entry point ────────────────────────────────────────────────────────────

    def scrape(self) -> List[dict]:
        self._warmup()
        jobs = []

        # emploi.cm pagination is 0-indexed:
        # page 1 = no param, page 2 = ?page=1, page 3 = ?page=2 ...
        for page in range(0, MAX_PAGES_PER_SITE):
            url = SEARCH_URL if page == 0 else f"{SEARCH_URL}?page={page}"
            logger.info(f"[{PORTAL_KEY}] Scraping page {page + 1} -> {url}")

            soup = self.get(url)
            if soup is None:
                logger.warning(f"[{PORTAL_KEY}] No response on page {page + 1} — stopping.")
                break

            if page == 0:
                self._dump_html(soup)

            cards = self._parse_cards(soup)
            if not cards:
                logger.info(f"[{PORTAL_KEY}] No cards on page {page + 1} — stopping.")
                break

            jobs.extend(cards)
            logger.info(
                f"[{PORTAL_KEY}] Page {page + 1}: {len(cards)} jobs. "
                f"Running total: {len(jobs)}"
            )

        logger.info(f"[{PORTAL_KEY}] Finished. Total scraped: {len(jobs)}")
        return jobs

    # ── Debug dump ─────────────────────────────────────────────────────────────

    def _dump_html(self, soup):
        debug_path = Path(DATA_DIR) / "debug_emploi_cm.html"
        debug_path.parent.mkdir(parents=True, exist_ok=True)
        debug_path.write_text(soup.prettify(), encoding="utf-8")
        logger.info(f"[{PORTAL_KEY}] Raw HTML saved -> {debug_path}")

    # ── Parse all cards on one page ────────────────────────────────────────────

    def _parse_cards(self, soup) -> List[dict]:
        """
        The outer wrapper has TWO classes: 'card' and 'card-job'.
        We select by card-job-detail (always present inside every card)
        then walk up to find the data-href on the parent.
        """
        jobs = []

        # Select the inner detail divs — confirmed present in every card
        detail_divs = soup.select("div.card-job-detail")
        logger.debug(f"[{PORTAL_KEY}] Found {len(detail_divs)} card-job-detail divs.")

        for detail in detail_divs:
            # Walk up to the outer card wrapper that holds data-href
            outer = detail.find_parent("div", attrs={"data-href": True})
            if outer is None:
                # data-href might be on the detail div itself in some variants
                outer = detail if detail.get("data-href") else None
            if outer is None:
                logger.debug(f"[{PORTAL_KEY}] Could not find data-href parent — skipping.")
                continue

            # ── URL ────────────────────────────────────────────────────────────
            data_href = outer.get("data-href", "")
            url = data_href if data_href.startswith("http") else BASE_URL + data_href

            # ── Title ──────────────────────────────────────────────────────────
            title_tag = detail.select_one("h3 a") or detail.select_one("h2 a")
            title = self.clean(title_tag.get_text()) if title_tag else ""

            # ── Company ────────────────────────────────────────────────────────
            company_tag = detail.select_one("a.card-job-company")
            company = self.clean(company_tag.get_text()) if company_tag else ""

            # ── Description snippet ────────────────────────────────────────────
            desc_tag = detail.select_one("div.card-job-description p")
            description = self.clean(desc_tag.get_text()) if desc_tag else ""

            # ── Structured <li> fields ─────────────────────────────────────────
            # All metadata lives in <li> tags. Each <li> has plain text label
            # and a <strong> child with the value.
            li_data = self._parse_li_fields(detail)

            skills_raw  = li_data.get("competences", "")
            city        = li_data.get("region", "")
            experience  = li_data.get("experience", "")

            # ── Date ──────────────────────────────────────────────────────────
            time_tag = detail.select_one("time")
            date_posted = (
                time_tag.get("datetime") or self.clean(time_tag.get_text())
                if time_tag else ""
            )

            if not title:
                logger.debug(f"[{PORTAL_KEY}] Skipping card with empty title.")
                continue

            jobs.append(self.make_job(
                title=title,
                company=company,
                city=city,
                experience=experience,
                skills_raw=skills_raw,
                description=description,
                url=url,
                date_posted=date_posted,
            ))

        return jobs

    # ── Parse <li> metadata fields ─────────────────────────────────────────────

    def _parse_li_fields(self, detail) -> dict:
        """
        Reads all <li> elements inside the card and returns a dict:
          {
            "competences": "API - BACK END - DOCKER - GIT ...",
            "region":      "Douala & Yaoundé",
            "experience":  "Expérience entre 2 ans et 5 ans et plus",
          }

        Each <li> looks like:
          <li>Compétences clés : <strong>API - BACK END - ...</strong></li>
        We read the text of the <li> to identify the field, then grab
        the <strong> child for the clean value.
        """
        result = {}

        # Map of text fragments -> result key
        FIELD_MAP = {
            "Comp\u00e9tences cl\u00e9s":  "competences",   # Compétences clés
            "Competences cles":              "competences",
            "Region de":                     "region",
            "R\u00e9gion de":                "region",       # Région de
            "Niveau d":                      "experience",   # Niveau d'expérience
            "Niveau d\u2019exp":             "experience",
        }

        for li in detail.select("ul li"):
            li_text = li.get_text(" ", strip=True)
            strong  = li.select_one("strong")
            value   = self.clean(strong.get_text()) if strong else ""

            if not value:
                continue

            for fragment, key in FIELD_MAP.items():
                if fragment in li_text:
                    # Don't overwrite a competences hit with an experience hit
                    if key not in result:
                        result[key] = value
                    break

        return result
