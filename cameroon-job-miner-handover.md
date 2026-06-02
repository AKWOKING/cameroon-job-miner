# Cameroon Tech Job Market Miner — Project Handover

**Student:** AKWO MAKEMBE KING  
**Course:** Data Mining & Applications, 2025/2026  
**GitHub:** https://github.com/AKWOKING/cameroon-job-miner  
**Live dashboard:** https://cameroon-job-miner.onrender.com  
**Tech stack:** Python, Streamlit, SQLite, Render.com (free tier)

---

## Project Summary

Automated web mining system that scrapes Cameroonian tech job portals, extracts in-demand skills via bilingual (FR/EN) NLP, runs Apriori association rule mining and K-Means clustering, and presents results on a live public Streamlit dashboard.

---

## Deliverables Status

| Deliverable | Status |
|---|---|
| Modular scraping system (4 portals) | ✅ Built and on GitHub |
| SQLite DB with weekly updates | ✅ GitHub Actions every Monday 03:00 UTC |
| Bilingual skill taxonomy CSV | ✅ 120 canonical skills, 343 aliases |
| Data mining report | ⬜ **NOT DONE — next task** |
| Live Streamlit dashboard | ✅ Live on Render |
| 5 techniques demonstrated | ✅ All implemented |

---

## Project Structure

```
cameroon-job-miner/
├── scrapers/
│   ├── base_scraper.py        # httpx + BeautifulSoup base class
│   ├── emploi_cm.py           # ✅ Working — main data source
│   ├── talent_cm.py           # ✅ Working (4 jobs only, global aggregator)
│   ├── expertini_cm.py        # ❌ Cloudflare 403 — permanently blocked
│   ├── workconnect.py         # ❌ Needs Selenium + ChromeDriver (CDN blocked)
│   ├── newjobscm.py           # ✅ Added by student — PAGINATION BUG (see below)
│   └── __init__.py
├── pipeline/
│   ├── cleaner.py             # City normalise, lang detect, skill extraction
│   └── miner.py               # Apriori + K-Means
├── data/
│   ├── jobs.db                # SQLite (committed to repo)
│   ├── skill_taxonomy.csv     # 120 skills, 343 aliases
│   └── exports/               # timestamped CSVs
├── config/settings.py
├── .github/workflows/weekly_scraper.yml
├── app.py                     # Streamlit dashboard (4 tabs)
├── run_scrapers.py
├── run_pipeline.py
├── render.yaml
└── requirements.txt
```

---

## Current DB State

```
emploi_cm:   ~167 jobs  ← main source, real scraped data
talent_cm:     ~5 jobs  ← global aggregator, low count expected
newjobscm:    ~20 jobs  ← PAGINATION BUG (scraping same page 10x)
demo seeds:    20 jobs  ← excluded from pipeline (url LIKE '%demo.example.com%')
TOTAL:        ~212 jobs in DB
```

---

## Pending Issue: newjobscm Pagination Bug

**Problem:** `https://newjobscameroon.com/jobs/?page=2` redirects 301 → homepage.  
The scraper is scraping the same 20 jobs 10 times (200 scraped, 0 new in DB).

**Correct pagination URL needs to be found.** The site is WordPress + WPJobBoard plugin.  
Likely correct patterns to try:
- `https://newjobscameroon.com/jobs/page/2/`  (WordPress standard)
- `https://newjobscameroon.com/?paged=2`
- AJAX/POST-based (would need Selenium)

**To fix:** Update `scrapers/newjobscm.py` pagination URL format.  
**Diagnostic scripts available:** `check_newjobs.py`, `diagnose.py` in project root.

---

## Latest Clean Pipeline Output (real data, 157 emploi.cm jobs)

```
Jobs cleaned       : 157
Avg skills / job   : 3.3
Taxonomy           : 343 aliases → 120 canonical skills

TOP 10 SKILLS:
 1. Java              34  (22%)
 2. JavaScript        26  (17%)
 3. CSS               24  (15%)
 4. Agile             23  (15%)
 5. Git               23  (15%)
 6. HTML              20  (13%)
 7. SAP/ERP           20  (13%)
 8. SQL               19  (12%)
 9. API               18  (12%)
10. Networking        16  (10%)

ASSOCIATION RULES (top 15 by lift, conf ≥ 0.4, lift ≥ 1.2):
PostgreSQL       → Docker + Git           conf=0.67  lift=7.63
Docker + Git     → PostgreSQL             conf=0.67  lift=7.63
PostgreSQL       → Agile + Git            conf=0.67  lift=6.24
Agile + Git      → PostgreSQL             conf=0.55  lift=6.24
MySQL            → Git + SQL              conf=0.40  lift=5.89
Git + SQL        → MySQL                  conf=0.86  lift=5.89
Oracle           → JavaScript + SQL       conf=0.50  lift=5.72
CI/CD + Java     → Oracle                 conf=0.67  lift=5.72
Oracle           → CI/CD + Java           conf=0.50  lift=5.72
JavaScript + SQL → Oracle                 conf=0.67  lift=5.72
jQuery           → JavaScript + MySQL     conf=0.67  lift=5.72
JavaScript+MySQL → jQuery                 conf=0.50  lift=5.72
CI/CD            → Java + Oracle          conf=0.60  lift=5.62
Java + Oracle    → CI/CD                  conf=0.55  lift=5.62
React            → CSS + Git              conf=0.75  lift=5.52

K-MEANS CLUSTERS (K=5, elbow method):
Cluster 0  IT Support / Sysadmin      65 jobs  63%  SAP/ERP, Networking, Monitoring, CRM
Cluster 2  Frontend Developer         18 jobs  18%  CSS, Java, JavaScript, HTML
Cluster 4  DevOps / Cloud Engineer    12 jobs  12%  Cloud Computing, Docker, Azure, Agile
Cluster 1  Full-Stack Developer        5 jobs   5%  MongoDB, JavaScript, Java, Git
Cluster 3  DevOps / Cloud Engineer     3 jobs   3%  MySQL, Oracle, Spring, CI/CD
```

---

## Key Technical Decisions & Fixes Made

### False Positive Fixes in cleaner.py
- **"R" language**: Single-char, only matches when R_CONTEXT present (RStudio, tidyverse, ggplot, SAS, SPSS etc.)
- **"Scala"**: CONTEXT_GUARDED_SKILLS — only matches when SCALA_CONTEXT present (Spark, Akka, sbt, JVM)
- Both were matching French word suffixes (développeur, fiscale, locale etc.)

### Demo Job Exclusion
- Demo seed jobs have `url LIKE '%demo.example.com%'`
- Excluded in cleaner.py SQL query before processing

### Cluster Archetype Scoring
- Score-based system: counts keyword matches per archetype
- Requires ≥2 matches for confident label
- Specific singles (Kubernetes, Flutter, Power BI etc.) can fire alone

### Taxonomy
- 120 canonical skills, 343 aliases
- Covers FR + EN variants
- Removed over-broad entries: Communication, Excel, PowerPoint, Word, Office 365, Gestion de Projet
- ERP tightened to SAP/ERP (only named ERP systems: SAP, Odoo, Sage, Oracle ERP, Dynamics)

---

## Immediate Next Steps

### 1. Fix newjobscm pagination (quick)
Try WordPress standard URL in `scrapers/newjobscm.py`:
```python
url = f"https://newjobscameroon.com/jobs/page/{page}/" if page > 1 else "https://newjobscameroon.com/jobs/"
```

### 2. Re-scrape and run pipeline with both portals
```powershell
python run_scrapers.py
python run_pipeline.py
```

### 3. Write the data mining report (main remaining deliverable)
**Report content to discuss before writing:**
- Format/template requirements from lecturer
- Page/word limit
- Whether code snippets are required
- Whether dashboard screenshots are needed

**Planned report sections:**
1. Introduction & Problem Statement (Cameroon tech market gap)
2. Data Collection Methodology (scraping architecture, 2 working portals, 3 blocked with reasons)
3. Data Cleaning & NLP Skill Extraction (taxonomy, false positive fixes, language detection)
4. Frequency Analysis — Top 30 skills with interpretation
5. Association Rule Mining — Top 15 rules with support/confidence/lift interpretation
6. K-Means Clustering — 5 archetypes with profiles
7. Dashboard overview
8. Limitations & Future Work
9. Conclusion

### 4. Commit final DB to GitHub
```powershell
git add data/jobs.db data/exports/
git commit -m "chore: final dataset with newjobscm"
git push
```

---

## Environment Setup (for new machine/chat)

```powershell
cd "C:\Users\JA 12\Documents\lvl 400\Second Semester\Data mining 2026\cameroon-job-miner-complete\cameroon-job-miner-final"
venv\Scripts\activate
python run_scrapers.py
python run_pipeline.py
python -m streamlit run app.py
```

## Dependencies
```
httpx>=0.27.0, requests>=2.31.0, beautifulsoup4>=4.12.3, lxml>=5.1.0
selenium>=4.18.1, webdriver-manager>=4.0.1
pandas>=2.0.0, langdetect>=1.0.9, nltk>=3.8.1
scikit-learn>=1.2.0, mlxtend>=0.22.0, numpy>=1.24.0
streamlit>=1.30.0, plotly>=5.18.0, python-dotenv>=1.0.0
```

---

## GitHub Actions Status
- Workflow: `.github/workflows/weekly_scraper.yml`
- Runs every Monday 03:00 UTC
- Commits updated `jobs.db` back to repo after each run
- Last manual run: ✅ Green
- Node.js 20 deprecation warning (non-critical, deadline is Sept 2026)

---

## Notes for Next Session
- The report is the ONLY remaining deliverable
- Discuss report format requirements with student before writing
- Pipeline output numbers above are from 157 real jobs — will improve once newjobscm pagination is fixed (~200 more jobs expected)
- Data is credible and clean enough to write the report even with just emploi.cm data if needed
- Student is confident and has been making independent fixes (built newjobscm scraper themselves)
