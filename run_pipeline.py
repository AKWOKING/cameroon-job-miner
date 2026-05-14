"""
run_pipeline.py
---------------
Master runner — Phases 2 & 3 in sequence.

Usage:
    python run_pipeline.py            # run all stages
    python run_pipeline.py --phase clean   # Phase 2 only
    python run_pipeline.py --phase mine    # Phase 3 only

Phase 1 (scraping) is run separately:
    python run_scrapers.py
"""

import argparse
import logging
import sys
import time

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("pipeline.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


def run_all(phase: str = "all"):
    start = time.time()

    if phase in ("all", "clean"):
        logger.info("\n" + "=" * 55)
        logger.info("  PHASE 2 — Cleaning & Skill Extraction")
        logger.info("=" * 55)
        from pipeline.cleaner import run_cleaning
        run_cleaning()

    if phase in ("all", "mine"):
        logger.info("\n" + "=" * 55)
        logger.info("  PHASE 3 — Association Rules + K-Means")
        logger.info("=" * 55)
        from pipeline.miner import run_mining
        run_mining()

    elapsed = time.time() - start
    logger.info(f"\nPipeline complete in {elapsed:.1f}s")
    logger.info("Launch dashboard: streamlit run app.py")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cameroon Job Market Miner — pipeline runner")
    parser.add_argument(
        "--phase",
        choices=["all", "clean", "mine"],
        default="all",
        help="Which phase to run (default: all)",
    )
    args = parser.parse_args()
    run_all(phase=args.phase)
