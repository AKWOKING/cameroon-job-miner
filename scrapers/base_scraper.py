"""
BaseScraper
-----------
Abstract base class that every portal-specific scraper inherits from.

Uses httpx instead of requests because httpx natively handles
Brotli compression (Content-Encoding: br) which emploi.cm uses
and which requests cannot decode even with manual workarounds.

Each subclass must implement:
  scrape()  ->  list[dict]

Required dict keys (use "" if unavailable):
  title, company, city, experience, skills_raw,
  description, url, date_posted, source
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from config.settings import (
    REQUEST_DELAY_MAX,
    REQUEST_DELAY_MIN,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    USER_AGENTS,
)

logger = logging.getLogger(__name__)


class BaseScraper(ABC):

    def __init__(self, portal_key: str):
        self.portal_key = portal_key
        merged_headers = {**REQUEST_HEADERS, "Accept-Encoding": "gzip, deflate"}
        self.client = httpx.Client(
            headers=merged_headers,
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
        )

    # ── Public interface ───────────────────────────────────────────────────────

    @abstractmethod
    def scrape(self) -> list:
        raise NotImplementedError

    # ── Shared helpers ─────────────────────────────────────────────────────────

    def get(self, url: str) -> Optional[BeautifulSoup]:
        """
        Politely fetch a URL and return a BeautifulSoup object.
        Returns None on any error so callers can skip gracefully.
        """
        self._polite_delay()
        try:
            logger.debug(f"[{self.portal_key}] GET {url}")
            response = self.client.get(url)
            response.raise_for_status()
            return BeautifulSoup(response.text, "lxml")
        except httpx.HTTPError as exc:
            logger.warning(f"[{self.portal_key}] Request failed: {exc} — {url}")
            return None

    def get_rotating(self, url: str, retries: int = 3) -> Optional[BeautifulSoup]:
        """
        Fetch with rotating User-Agent and Referer spoofing.
        Use this for sites that return 403 with a static header.
        Retries up to `retries` times with a fresh UA each attempt.
        """
        for attempt in range(1, retries + 1):
            self._polite_delay()
            ua = random.choice(USER_AGENTS)
            headers = {
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "fr-CM,fr;q=0.9,en-US;q=0.7,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Referer": "https://www.google.com/",
                "DNT": "1",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "cross-site",
            }
            try:
                logger.debug(f"[{self.portal_key}] GET (attempt {attempt}, UA: ...{ua[-30:]}) {url}")
                response = httpx.get(
                    url,
                    headers=headers,
                    timeout=REQUEST_TIMEOUT,
                    follow_redirects=True,
                )
                response.raise_for_status()
                return BeautifulSoup(response.text, "lxml")
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                logger.warning(f"[{self.portal_key}] HTTP {status} on attempt {attempt} — {url}")
                if status == 403 and attempt < retries:
                    wait = 3 * attempt
                    logger.info(f"[{self.portal_key}] Waiting {wait}s before retry...")
                    time.sleep(wait)
                else:
                    return None
            except httpx.HTTPError as exc:
                logger.warning(f"[{self.portal_key}] Request error on attempt {attempt}: {exc}")
                return None
        return None

    def update_headers(self, headers: dict):
        """Merge extra headers into the client (e.g. Referer per scraper)."""
        self.client.headers.update(headers)

    def _polite_delay(self):
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        logger.debug(f"[{self.portal_key}] Sleeping {delay:.1f}s")
        time.sleep(delay)

    @staticmethod
    def clean(text: Optional[str]) -> str:
        if not text:
            return ""
        return " ".join(text.split())

    def make_job(self, **kwargs) -> dict:
        defaults = {
            "title": "",
            "company": "",
            "city": "",
            "experience": "",
            "skills_raw": "",
            "description": "",
            "url": "",
            "date_posted": "",
            "source": self.portal_key,
        }
        defaults.update(kwargs)
        defaults["source"] = self.portal_key
        return defaults

    def __del__(self):
        try:
            self.client.close()
        except Exception:
            pass
