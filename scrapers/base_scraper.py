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
)

logger = logging.getLogger(__name__)


class BaseScraper(ABC):

    def __init__(self, portal_key: str):
        self.portal_key = portal_key
        # httpx.Client handles gzip and deflate automatically.
        # We explicitly override Accept-Encoding to exclude br and zstd —
        # Cloudflare-fronted sites (like emploi.cm) serve zstd when those
        # are advertised, and neither httpx nor requests can decode zstd.
        # Forcing gzip/deflate gets us clean, decodable responses.
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
        httpx automatically decompresses gzip, deflate, and brotli.
        """
        self._polite_delay()
        try:
            logger.debug(f"[{self.portal_key}] GET {url}")
            response = self.client.get(url)
            response.raise_for_status()
            # response.text is always a clean decoded string with httpx
            return BeautifulSoup(response.text, "lxml")
        except httpx.HTTPError as exc:
            logger.warning(f"[{self.portal_key}] Request failed: {exc} — {url}")
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
