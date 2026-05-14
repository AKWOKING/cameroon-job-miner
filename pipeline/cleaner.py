"""
pipeline/cleaner.py
-------------------
Phase 2 — Data Cleaning & NLP Skill Extraction

Steps:
  1. Load raw jobs from SQLite
  2. Normalise cities, titles, experience levels
  3. Detect language (fr / en) per listing
  4. Extract skills via bilingual taxonomy keyword matching
  5. Save cleaned + skill-tagged records back to SQLite (jobs_clean table)
  6. Export frequency tables as CSV

Usage:
    python -m pipeline.cleaner
"""

import logging
import re
import sqlite3
from pathlib import Path

import pandas as pd
from langdetect import detect, LangDetectException

from config.settings import DATA_DIR, DB_PATH

logger = logging.getLogger(__name__)

TAXONOMY_PATH = DATA_DIR / "skill_taxonomy.csv"
CLEAN_TABLE   = "jobs_clean"


# ── City normalisation map ─────────────────────────────────────────────────────
CITY_MAP = {
    # French variants → canonical English/French name
    "douala":      "Douala",
    "yaounde":     "Yaoundé",
    "yaoundé":     "Yaoundé",
    "yaounde cameroun": "Yaoundé",
    "douala cameroun":  "Douala",
    "bafoussam":   "Bafoussam",
    "bamenda":     "Bamenda",
    "garoua":      "Garoua",
    "maroua":      "Maroua",
    "ngaoundere":  "Ngaoundéré",
    "ngaoundéré":  "Ngaoundéré",
    "ebolowa":     "Ebolowa",
    "bertoua":     "Bertoua",
    "limbe":       "Limbé",
    "limbé":       "Limbé",
    "kribi":       "Kribi",
    "cameroon":    "Cameroun",
    "cameroun":    "Cameroun",
}

# ── Experience normalisation ───────────────────────────────────────────────────
def _normalise_experience(raw: str) -> str:
    """Map messy experience strings to clean buckets."""
    if not raw:
        return "Non précisé"
    r = raw.lower()
    if any(k in r for k in ["junior", "débutant", "0-1", "moins d'1", "< 1", "entry"]):
        return "Junior (0–1 an)"
    if any(k in r for k in ["1 an", "1-2", "1 à 2", "entre 1"]):
        return "1–2 ans"
    if any(k in r for k in ["2 ans", "2-5", "2 à 5", "entre 2"]):
        return "2–5 ans"
    if any(k in r for k in ["5 ans", "5-10", "5 à 10", "entre 5", "senior", "confirmé"]):
        return "5+ ans"
    if any(k in r for k in ["10 ans", "> 10", "10+"]):
        return "10+ ans"
    return "Non précisé"


# ── City extraction from description (fallback) ────────────────────────────────
CITY_KEYWORDS = list(CITY_MAP.keys())

def _extract_city(city_raw: str, description: str) -> str:
    """Normalise city from explicit field; if empty, scan description."""
    text = city_raw.lower().strip()
    for key, value in CITY_MAP.items():
        if key in text:
            return value
    # Fallback: scan description
    desc_lower = description.lower()
    for key, value in CITY_MAP.items():
        if key in desc_lower:
            return value
    return city_raw.title() if city_raw else "Non précisé"


# ── Language detection ─────────────────────────────────────────────────────────
def _detect_language(text: str) -> str:
    if not text or len(text) < 20:
        return "unknown"
    try:
        return detect(text[:500])
    except LangDetectException:
        return "unknown"


# ── Load taxonomy ──────────────────────────────────────────────────────────────
def load_taxonomy() -> dict:
    """
    Returns a dict: { alias_lower: canonical_name }
    Built from skill_taxonomy.csv.
    """
    if not TAXONOMY_PATH.exists():
        raise FileNotFoundError(f"Skill taxonomy not found at {TAXONOMY_PATH}")
    df = pd.read_csv(TAXONOMY_PATH, dtype=str).fillna("")
    mapping = {}
    for _, row in df.iterrows():
        canonical = row["canonical"].strip()
        # Include canonical itself
        mapping[canonical.lower()] = canonical
        # Include all aliases
        for alias in row["aliases"].split(";"):
            alias = alias.strip().lower()
            if alias:
                mapping[alias] = canonical
    logger.info(f"Taxonomy loaded: {len(mapping)} alias entries → {len(set(mapping.values()))} canonical skills")
    return mapping


# ── Skill extraction ───────────────────────────────────────────────────────────
def extract_skills(text: str, taxonomy: dict) -> list:
    """
    Given combined text (skills_raw + description), return a sorted list
    of unique canonical skill names found via case-insensitive keyword matching.
    Uses word-boundary matching to avoid false positives (e.g. 'R' in 'React').
    """
    if not text:
        return []
    text_lower = text.lower()
    found = set()

    # Sort aliases by length descending — match longer phrases first
    for alias in sorted(taxonomy.keys(), key=len, reverse=True):
        # Use word boundaries for short aliases (≤ 3 chars) to reduce noise
        if len(alias) <= 3:
            pattern = r'(?<![a-z0-9])' + re.escape(alias) + r'(?![a-z0-9])'
        else:
            pattern = re.escape(alias)
        if re.search(pattern, text_lower):
            found.add(taxonomy[alias])

    return sorted(found)


# ── Main cleaning pipeline ─────────────────────────────────────────────────────
def run_cleaning():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("=== Phase 2: Cleaning & Skill Extraction ===")

    taxonomy = load_taxonomy()

    conn = sqlite3.connect(DB_PATH)

    # Check if raw jobs table exists and has data
    count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    logger.info(f"Raw jobs in DB: {count}")

    if count == 0:
        logger.warning("No jobs found in DB. Run run_scrapers.py first, or the demo seed will be used.")
        _seed_demo_data(conn)
        count = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        logger.info(f"After seeding: {count} jobs")

    # Load all raw jobs
    df = pd.read_sql("SELECT * FROM jobs", conn)
    logger.info(f"Loaded {len(df)} raw records")

    # ── Clean & enrich each row ────────────────────────────────────────────────
    records = []
    for _, row in df.iterrows():
        combined_text = f"{row.get('skills_raw', '')} {row.get('description', '')}"

        city       = _extract_city(str(row.get("city", "")), str(row.get("description", "")))
        experience = _normalise_experience(str(row.get("experience", "")))
        language   = _detect_language(combined_text)
        skills     = extract_skills(combined_text, taxonomy)
        skills_str = "|".join(skills)  # pipe-separated for easy splitting later

        records.append({
            "raw_id":       row["id"],
            "hash":         row["hash"],
            "title":        str(row.get("title", "")).strip(),
            "company":      str(row.get("company", "")).strip(),
            "city":         city,
            "experience":   experience,
            "language":     language,
            "skills_raw":   str(row.get("skills_raw", "")),
            "skills_extracted": skills_str,
            "skill_count":  len(skills),
            "description":  str(row.get("description", ""))[:1000],  # truncate for DB
            "url":          str(row.get("url", "")),
            "date_posted":  str(row.get("date_posted", "")),
            "source":       str(row.get("source", "")),
            "scraped_at":   str(row.get("scraped_at", "")),
        })

    clean_df = pd.DataFrame(records)
    logger.info(f"Cleaned {len(clean_df)} records")
    logger.info(f"Skills extracted — avg per job: {clean_df['skill_count'].mean():.1f}")

    # ── Save to jobs_clean table ───────────────────────────────────────────────
    conn.execute(f"DROP TABLE IF EXISTS {CLEAN_TABLE}")
    clean_df.to_sql(CLEAN_TABLE, conn, if_exists="replace", index=False)
    conn.commit()
    logger.info(f"Saved to SQLite table: {CLEAN_TABLE}")

    # ── Generate frequency table ───────────────────────────────────────────────
    freq_df = _build_frequency_table(clean_df)
    freq_path = DATA_DIR / "exports" / "skill_frequency.csv"
    freq_path.parent.mkdir(parents=True, exist_ok=True)
    freq_df.to_csv(freq_path, index=False, encoding="utf-8-sig")
    logger.info(f"Frequency table saved → {freq_path}")

    conn.close()

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 55)
    print("  PHASE 2 COMPLETE — Cleaning & Extraction")
    print("=" * 55)
    print(f"  Jobs cleaned       : {len(clean_df)}")
    print(f"  Avg skills / job   : {clean_df['skill_count'].mean():.1f}")
    print(f"  Top 10 skills:")
    for i, row in freq_df.head(10).iterrows():
        print(f"    {i+1:>2}. {row['skill']:<25} {row['count']:>4}  ({row['pct']:.0f}%)")
    print(f"\n  Table : {CLEAN_TABLE} (jobs.db)")
    print(f"  CSV   : {freq_path}")
    print("=" * 55 + "\n")

    return clean_df, freq_df


def _build_frequency_table(df: pd.DataFrame) -> pd.DataFrame:
    """Count how many job listings mention each skill."""
    skill_counts = {}
    for skills_str in df["skills_extracted"]:
        if not skills_str:
            continue
        for skill in skills_str.split("|"):
            skill = skill.strip()
            if skill:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1

    total = len(df)
    rows = [
        {"skill": skill, "count": count, "pct": round(100 * count / total, 1)}
        for skill, count in sorted(skill_counts.items(), key=lambda x: -x[1])
    ]
    return pd.DataFrame(rows)


def _seed_demo_data(conn: sqlite3.Connection):
    """
    Insert realistic demo jobs so the pipeline can be tested without scraping.
    These reflect the kinds of listings actually found on Cameroonian portals.
    """
    import hashlib
    from datetime import datetime

    demo_jobs = [
        ("Développeur Full Stack React/Node.js", "Orange Cameroun", "Douala", "2–5 ans",
         "React - Node.js - MongoDB - Docker - Git",
         "Nous recherchons un développeur full stack maîtrisant React, Node.js, MongoDB. Expérience avec Docker et Git requise.",
         "emploi_cm"),
        ("Ingénieur DevOps", "Afriland First Bank", "Yaoundé", "Expérience entre 2 ans et 5 ans",
         "Docker - Kubernetes - AWS - CI/CD - Linux",
         "Poste d'ingénieur DevOps. Compétences requises: Docker, Kubernetes, AWS, pipelines CI/CD, administration Linux.",
         "emploi_cm"),
        ("Développeur Mobile Android/iOS", "MTN Cameroun", "Douala", "Junior",
         "Android - Flutter - Kotlin - Git - REST API",
         "Junior mobile developer needed. Skills: Android, Flutter, Kotlin, REST APIs, Git.",
         "talent_cm"),
        ("Data Scientist", "Société Générale Cameroun", "Yaoundé", "5 ans",
         "Python - Machine Learning - TensorFlow - SQL - Power BI",
         "Data Scientist avec expérience en Machine Learning, Python, TensorFlow, analyse de données, SQL.",
         "talent_cm"),
        ("Développeur Backend Python/Django", "CAMTEL", "Yaoundé", "2 ans",
         "Python - Django - PostgreSQL - REST API - Git",
         "Développeur backend Python Django, base de données PostgreSQL, API REST, versioning Git.",
         "expertini_cm"),
        ("Administrateur Système Linux", "Ministère du Numérique", "Yaoundé", "3 ans",
         "Linux - Bash - Networking - Apache - Nginx",
         "Administration système Linux, scripting Bash, réseaux TCP/IP, serveurs web Apache et Nginx.",
         "expertini_cm"),
        ("Développeur Web PHP/Laravel", "StartupCM", "Douala", "1 an",
         "PHP - Laravel - MySQL - JavaScript - Bootstrap",
         "Développeur web PHP Laravel, MySQL, JavaScript, Bootstrap pour startup camerounaise.",
         "workconnect"),
        ("Chef de Projet IT Agile", "Ecobank Cameroun", "Douala", "5 ans",
         "Agile - Scrum - Jira - SQL - Power BI",
         "Chef de projet IT, méthodes Agile/Scrum, Jira, maîtrise SQL et Power BI.",
         "workconnect"),
        ("Développeur Frontend Vue.js", "Interswitch", "Douala", "2 ans",
         "Vue.js - JavaScript - HTML - CSS - REST API",
         "Développeur frontend Vue.js, HTML5, CSS3, intégration d'APIs REST.",
         "emploi_cm"),
        ("Ingénieur Sécurité Informatique", "Express Union", "Yaoundé", "5 ans",
         "Cybersecurity - Linux - Networking - Python - Docker",
         "Ingénieur en sécurité informatique, audit de vulnérabilités, Linux, réseaux, Python.",
         "emploi_cm"),
        ("Développeur React Native", "AgriTech Cameroun", "Bafoussam", "2 ans",
         "React Native - JavaScript - Firebase - REST API - Git",
         "Mobile developer React Native, Firebase, REST API integration, Git versioning.",
         "talent_cm"),
        ("Analyste de Données", "BICEC", "Douala", "3 ans",
         "Python - SQL - Pandas - Power BI - Excel",
         "Data analyst: Python, SQL, Pandas, Power BI, analyse et visualisation de données.",
         "talent_cm"),
        ("Développeur Java Spring Boot", "Camair-Co", "Douala", "3 ans",
         "Java - Spring Boot - MySQL - Docker - Git - REST API",
         "Développeur Java Spring Boot, MySQL, Docker, intégration continue Git.",
         "expertini_cm"),
        ("Développeur WordPress", "Agence Web Douala", "Douala", "1 an",
         "WordPress - PHP - CSS - HTML - JavaScript",
         "Créer et maintenir des sites WordPress, personnalisation de thèmes PHP, CSS, JavaScript.",
         "workconnect"),
        ("Ingénieur Machine Learning", "DataCM", "Yaoundé", "3 ans",
         "Python - Machine Learning - NLP - Scikit-learn - TensorFlow - SQL",
         "ML engineer: Python, scikit-learn, TensorFlow, NLP, SQL databases.",
         "emploi_cm"),
        ("Développeur Node.js/Express", "Jumia Cameroun", "Douala", "2 ans",
         "Node.js - Express.js - MongoDB - Docker - REST API - Git",
         "Backend Node.js Express developer, MongoDB, Docker, RESTful APIs.",
         "talent_cm"),
        ("Responsable Infrastructure IT", "Total Cameroun", "Douala", "7 ans",
         "Linux - Networking - Kubernetes - AWS - CI/CD",
         "Manage IT infrastructure: Linux servers, networking, Kubernetes, cloud AWS.",
         "expertini_cm"),
        ("Développeur Angular TypeScript", "Fintech Yaoundé", "Yaoundé", "2 ans",
         "Angular - TypeScript - HTML - CSS - REST API",
         "Frontend Angular developer with TypeScript, REST API integration.",
         "workconnect"),
        ("Ingénieur Data / Big Data", "Telco Africa", "Douala", "4 ans",
         "Python - Spark - SQL - Hadoop - Machine Learning",
         "Big Data engineer, Apache Spark, Hadoop, SQL, Python, machine learning pipelines.",
         "emploi_cm"),
        ("Développeur iOS Swift", "Maviance", "Yaoundé", "2 ans",
         "iOS - Swift - REST API - Git - Firebase",
         "iOS Swift developer, REST APIs, Firebase, Git. Application mobile fintech.",
         "talent_cm"),
    ]

    scraped_at = datetime.utcnow().isoformat()
    for title, company, city, exp, skills_raw, desc, source in demo_jobs:
        key = f"{title.lower()}|{company.lower()}|{source}"
        h = hashlib.sha256(key.encode()).hexdigest()[:16]
        try:
            conn.execute(
                """INSERT OR IGNORE INTO jobs
                   (hash,title,company,city,experience,skills_raw,description,url,date_posted,source,scraped_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (h, title, company, city, exp, skills_raw, desc,
                 f"https://demo.example.com/{h}", "2026-04-01", source, scraped_at),
            )
        except Exception as e:
            logger.warning(f"Seed insert failed: {e}")
    conn.commit()
    logger.info(f"Seeded {len(demo_jobs)} demo jobs.")


if __name__ == "__main__":
    run_cleaning()
