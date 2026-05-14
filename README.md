# 🇨🇲 Cameroon Tech Job Market Miner

> Automated web mining & skill trend analysis for the Cameroonian technology sector  
> Academic project — Data Mining & Applications, 2025/2026

---

## What it does

Scrapes tech job listings from **4 Cameroonian job portals** every week, extracts in-demand skills using a bilingual (French/English) NLP pipeline, runs association rule mining and K-Means clustering, then presents everything in a **live public Streamlit dashboard**.

| Portal | URL |
|---|---|
| Emploi.cm | https://www.emploi.cm |
| Talent.cm | https://cm.talent.com |
| Expertini.cm | https://cm.expertini.com |
| WorkConnect | https://www.workconnectjob.com |

---

## Project phases

| Phase | Weeks | Status | Built |
|-------|-------|--------|-------|
| **1 — Scraping** | 1–2 | ✅ | 4 scraper classes, SQLite storage, CSV export |
| **2 — Processing** | 3–4 | ✅ | Cleaning, bilingual taxonomy, NLP skill extraction |
| **3 — Mining & Dashboard** | 5–6 | ✅ | Apriori rules, K-Means, Streamlit dashboard |
| **4 — Deploy & Document** | 7–8 | ✅ | Render.com config, GitHub Actions, full docs |

---

## Quick start

```bash
# 1. Set up
git clone https://github.com/AKWOKING/cameroon-job-miner.git
cd cameroon-job-miner
python -m venv venv && venv\Scripts\activate   # Windows
pip install -r requirements.txt

# 2. Scrape (Phase 1)
python run_scrapers.py

# 3. Clean + Mine (Phases 2 & 3)
python run_pipeline.py

# 4. Dashboard
streamlit run app.py
```

---

## Project structure

```
cameroon-job-miner/
├── scrapers/                    Phase 1 — web scraping
│   ├── base_scraper.py          httpx + BeautifulSoup base class
│   ├── emploi_cm.py
│   ├── talent_cm.py
│   ├── expertini_cm.py
│   └── workconnect.py           auto-falls back to Selenium
│
├── pipeline/                    Phases 2 & 3 — processing & mining
│   ├── cleaner.py               normalise, detect language, extract skills
│   └── miner.py                 Apriori association rules + K-Means
│
├── data/
│   ├── jobs.db                  SQLite (all tables)
│   ├── skill_taxonomy.csv       102 canonical skills, 276 aliases, FR+EN
│   └── exports/                 timestamped CSVs
│
├── config/settings.py           all configuration
├── .github/workflows/
│   └── weekly_scraper.yml       runs every Monday 03:00 UTC
├── app.py                       Streamlit dashboard
├── run_scrapers.py              Phase 1 entry point
├── run_pipeline.py              Phase 2+3 entry point
├── render.yaml                  Render.com deploy config
└── requirements.txt
```

---

## Data mining techniques

| # | Technique | Where | Output |
|---|-----------|-------|--------|
| 1 | Web scraping (httpx + BS4 + Selenium) | `scrapers/` | Raw job records |
| 2 | Bilingual NLP skill extraction | `pipeline/cleaner.py` | `skills_extracted` column |
| 3 | Frequency ranking | `pipeline/cleaner.py` | Top N skills per filter |
| 4 | Association rule mining (Apriori) | `pipeline/miner.py` | Skill co-occurrence rules |
| 5 | Unsupervised clustering (K-Means) | `pipeline/miner.py` | Role archetypes |

---

## Deployment on Render.com (free tier)

1. Push repo to GitHub  
2. Render → New Web Service → connect repo  
3. `render.yaml` is auto-detected — no manual config needed  
4. Dashboard live at `https://cameroon-job-miner.onrender.com`

Data stays fresh via **GitHub Actions** weekly cron — no paid Render plan needed.

---

## Skill taxonomy

`data/skill_taxonomy.csv` — 102 canonical skills, 10 categories, 276 aliases (FR+EN).  
Open CSV — contributions welcome.

---

## Configuration

Edit `config/settings.py`:

| Setting | Default | Notes |
|---------|---------|-------|
| `REQUEST_DELAY_MIN/MAX` | 2–5s | Politeness delay between requests |
| `MAX_PAGES_PER_SITE` | 10 | Increase once pagination is verified |
| `LOG_LEVEL` | INFO | Set DEBUG to diagnose HTML changes |

---

## Author

**AKWO MAKEMBE KING** — Data Mining & Applications, 2025/2026  
*Total cost: XAF 0. Entirely open-source.*
