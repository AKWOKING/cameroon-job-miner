"""
run_scrapers.py
---------------
Main entry point for Phase 1.

Usage (from the project root):
    python run_scrapers.py              # run all enabled scrapers
    python run_scrapers.py --portal emploi_cm   # run a single portal

What it does:
  1. Runs each enabled scraper
  2. Saves results to SQLite  (data/jobs.db)
  3. Exports a timestamped CSV (data/exports/jobs_YYYYMMDD_HHMMSS.csv)
  4. Prints a summary to the console
"""

from typing import Optional

import argparse
import hashlib
import logging
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

from config.settings import DB_PATH, EXPORTS_DIR, LOG_LEVEL, PORTALS
from scrapers import (
    EmploiCmScraper,
    ExpertiniCmScraper,
    TalentCmScraper,
    WorkConnectScraper,
    NewJobsCmScraper,
)

# ── Logging setup ──────────────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("scraper.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)

# ── Scraper registry ───────────────────────────────────────────────────────────
SCRAPER_MAP = {
    "emploi_cm":    EmploiCmScraper,
    "talent_cm":    TalentCmScraper,
    "expertini_cm": ExpertiniCmScraper,
    "workconnect":  WorkConnectScraper,
    "newjobscm":    NewJobsCmScraper,
}


# ── Database ───────────────────────────────────────────────────────────────────

def init_db(db_path: Path) -> sqlite3.Connection:
    """Create the jobs table if it doesn't exist yet."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            hash          TEXT    UNIQUE,          -- deduplication key
            title         TEXT,
            company       TEXT,
            city          TEXT,
            experience    TEXT,
            skills_raw    TEXT,
            description   TEXT,
            url           TEXT,
            date_posted   TEXT,
            source        TEXT,
            scraped_at    TEXT                     -- ISO timestamp
        )
    """)
    conn.commit()
    return conn


def make_hash(job: dict) -> str:
    """
    A job is considered a duplicate if title + company + source are the same.
    This handles the same listing appearing on multiple scrape runs.
    """
    key = f"{job['title'].lower()}|{job['company'].lower()}|{job['source']}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def save_jobs(conn: sqlite3.Connection, jobs: list[dict]) -> int:
    """
    Insert jobs into SQLite, skipping duplicates (INSERT OR IGNORE).
    Returns the number of new rows inserted.
    """
    scraped_at = datetime.now(datetime.UTC).isoformat() if hasattr(datetime, 'UTC') else datetime.utcnow().isoformat()
    rows = []
    for job in jobs:
        job_hash = make_hash(job)
        rows.append((
            job_hash,
            job.get("title", ""),
            job.get("company", ""),
            job.get("city", ""),
            job.get("experience", ""),
            job.get("skills_raw", ""),
            job.get("description", ""),
            job.get("url", ""),
            job.get("date_posted", ""),
            job.get("source", ""),
            scraped_at,
        ))

    before = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    conn.executemany(
        """
        INSERT OR IGNORE INTO jobs
          (hash, title, company, city, experience, skills_raw,
           description, url, date_posted, source, scraped_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        rows,
    )
    conn.commit()
    after = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    return after - before


# ── CSV export ─────────────────────────────────────────────────────────────────

def export_csv(conn: sqlite3.Connection) -> Path:
    """Export the full jobs table to a timestamped CSV file."""
    EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(datetime.UTC).strftime("%Y%m%d_%H%M%S") if hasattr(datetime, 'UTC') else datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    csv_path  = EXPORTS_DIR / f"jobs_{timestamp}.csv"

    df = pd.read_sql("SELECT * FROM jobs", conn)
    df.to_csv(csv_path, index=False, encoding="utf-8-sig")  # utf-8-sig for Excel compat
    return csv_path


# ── Main ───────────────────────────────────────────────────────────────────────

def run(portal_filter: Optional[str] = None):
    conn = init_db(DB_PATH)
    total_new = 0
    results_summary = []

    for key, scraper_cls in SCRAPER_MAP.items():
        # Honour --portal flag and the 'enabled' setting in config
        if portal_filter and key != portal_filter:
            continue
        if not PORTALS.get(key, {}).get("enabled", True):
            logger.info(f"Skipping {key} (disabled in config)")
            continue

        logger.info(f"\n{'='*50}")
        logger.info(f"Starting scraper: {key}")
        logger.info(f"{'='*50}")

        try:
            scraper = scraper_cls()
            jobs    = scraper.scrape()
            new     = save_jobs(conn, jobs)
            total_new += new
            results_summary.append((key, len(jobs), new))
            logger.info(f"[{key}] Scraped {len(jobs)} | New in DB: {new}")
        except Exception as exc:
            logger.error(f"[{key}] Scraper failed: {exc}", exc_info=True)
            results_summary.append((key, 0, 0))

    # Export CSV after all scrapers complete
    csv_path = export_csv(conn)
    conn.close()

    # ── Summary table ──────────────────────────────────────────────────────────
    print("\n" + "=" * 50)
    print("  SCRAPING COMPLETE")
    print("=" * 50)
    print(f"  {'Portal':<20} {'Scraped':>8} {'New in DB':>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*10}")
    for key, scraped, new in results_summary:
        print(f"  {key:<20} {scraped:>8} {new:>10}")
    print(f"  {'-'*20} {'-'*8} {'-'*10}")
    print(f"  {'TOTAL':<20} {sum(s for _,s,_ in results_summary):>8} {total_new:>10}")
    print(f"\n  DB   : {DB_PATH}")
    print(f"  CSV  : {csv_path}")
    print("=" * 50 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cameroon Job Market Miner — scraper runner")
    parser.add_argument(
        "--portal",
        choices=list(SCRAPER_MAP.keys()),
        default=None,
        help="Run a single portal instead of all (e.g. --portal emploi_cm)",
    )
    args = parser.parse_args()
    run(portal_filter=args.portal)
