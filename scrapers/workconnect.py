"""
WorkConnectScraper
------------------
Scrapes tech job listings from workconnectjob.com.

WorkConnect is a React-based site. We first try a plain requests fetch.
If the job cards are absent (JS-rendered), we fall back automatically
to Selenium with a headless Chrome driver.
"""

import logging

from config.settings import MAX_PAGES_PER_SITE, PORTALS, REQUEST_DELAY_MIN
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

PORTAL_KEY = "workconnect"
BASE_URL   = PORTALS[PORTAL_KEY]["base_url"]
SEARCH_URL = PORTALS[PORTAL_KEY]["search_url"]


def _get_selenium_driver():
    """
    Lazily import and initialise a headless Chrome driver.
    Only called if the static fetch doesn't find any job cards.
    Requires: pip install selenium webdriver-manager
    """
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()
    options.add_argument("--headless=new")          # headless mode
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1280,900")
    options.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )

    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)


class WorkConnectScraper(BaseScraper):

    def __init__(self):
        super().__init__(PORTAL_KEY)
        self._driver = None   # only initialised if needed

    # ── Entry point ────────────────────────────────────────────────────────────

    def scrape(self) -> list[dict]:
        jobs = []
        try:
            for page in range(1, MAX_PAGES_PER_SITE + 1):
                url = f"{SEARCH_URL}?page={page}" if page > 1 else SEARCH_URL
                logger.info(f"[{PORTAL_KEY}] Scraping page {page} → {url}")

                cards = self._get_cards(url)
                if not cards:
                    logger.info(f"[{PORTAL_KEY}] No cards on page {page} — stopping.")
                    break

                for card in cards:
                    jobs.append(card)
                logger.info(f"[{PORTAL_KEY}] Page {page}: {len(cards)} listings found.")

        finally:
            self._close_driver()

        logger.info(f"[{PORTAL_KEY}] Total scraped: {len(jobs)}")
        return jobs

    # ── Fetch + auto-fallback ──────────────────────────────────────────────────

    def _get_cards(self, url: str) -> list[dict]:
        """Try static fetch first; fall back to Selenium if no cards found."""
        soup = self.get(url)
        if soup:
            cards = self._parse_cards(soup)
            if cards:
                return cards
            logger.info(f"[{PORTAL_KEY}] Static fetch found no cards — trying Selenium.")

        return self._selenium_get_cards(url)

    # ── Static HTML parsing ────────────────────────────────────────────────────

    def _parse_cards(self, soup) -> list[dict]:
        jobs = []

        # WorkConnect wraps each listing in a card div
        cards = (
            soup.select("div[class*='job-card']")
            or soup.select("div[class*='JobCard']")
            or soup.select("article[class*='job']")
            or soup.select("div[class*='listing']")
        )

        for card in cards:
            title_tag = (
                card.select_one("h2")
                or card.select_one("h3")
                or card.select_one("[class*='title']")
            )
            if not title_tag:
                continue
            title = self.clean(title_tag.get_text())

            # URL
            a_tag = card.select_one("a[href]")
            href  = a_tag.get("href", "") if a_tag else ""
            url   = href if href.startswith("http") else BASE_URL + href

            company_tag = card.select_one("[class*='company']") or card.select_one("[class*='employer']")
            company = self.clean(company_tag.get_text()) if company_tag else ""

            city_tag = card.select_one("[class*='location']") or card.select_one("[class*='city']")
            city = self.clean(city_tag.get_text()) if city_tag else ""

            desc_tag = card.select_one("p") or card.select_one("[class*='description']")
            description = self.clean(desc_tag.get_text()) if desc_tag else ""

            date_tag = card.select_one("time") or card.select_one("[class*='date']")
            date_posted = self.clean(date_tag.get_text()) if date_tag else ""

            jobs.append(self.make_job(
                title=title,
                company=company,
                city=city,
                description=description,
                url=url,
                date_posted=date_posted,
            ))

        return jobs

    # ── Selenium fallback ──────────────────────────────────────────────────────

    def _selenium_get_cards(self, url: str) -> list[dict]:
        import time
        from bs4 import BeautifulSoup

        try:
            if self._driver is None:
                logger.info(f"[{PORTAL_KEY}] Initialising Selenium driver...")
                self._driver = _get_selenium_driver()

            self._driver.get(url)
            time.sleep(REQUEST_DELAY_MIN + 2)   # wait for JS to render

            soup = BeautifulSoup(self._driver.page_source, "lxml")
            cards = self._parse_cards(soup)

            if not cards:
                logger.warning(f"[{PORTAL_KEY}] Selenium found no cards either at {url}")

            return cards

        except Exception as exc:
            err = str(exc)
            if "offline" in err.lower() or "reach host" in err.lower() or "net::" in err.lower():
                logger.warning(
                    f"[{PORTAL_KEY}] Selenium could not reach ChromeDriver CDN "
                    f"(network restricted). WorkConnect will be skipped this run.\n"
                    f"  Fix: ensure internet access, or install ChromeDriver manually:\n"
                    f"  1. Download from https://googlechromelabs.github.io/chrome-for-testing/\n"
                    f"  2. Add chromedriver.exe to your PATH\n"
                    f"  Then re-run the scraper."
                )
            else:
                logger.error(f"[{PORTAL_KEY}] Selenium error: {exc}")
            return []

    def _close_driver(self):
        if self._driver:
            try:
                self._driver.quit()
            except Exception:
                pass
            self._driver = None
