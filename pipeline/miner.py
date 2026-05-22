"""
pipeline/miner.py
-----------------
Phase 3 — Data Mining

Techniques applied:
  1. Association Rule Mining (Apriori via mlxtend)
     → discovers skill pairs / triplets that co-occur frequently
     → e.g. "React + Node.js appear together in 68% of full-stack listings"

  2. K-Means Clustering (scikit-learn)
     → vectorises jobs as binary skill feature vectors
     → groups into K clusters, elbow method selects K
     → each cluster is labelled as a role archetype

Results saved to:
  - SQLite: association_rules, job_clusters tables
  - CSV exports: association_rules.csv, job_clusters.csv, cluster_profiles.csv

Usage:
    python -m pipeline.miner
"""

import logging
import sqlite3
import warnings

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import MultiLabelBinarizer

from config.settings import DATA_DIR, DB_PATH

warnings.filterwarnings("ignore")

logger = logging.getLogger(__name__)

CLEAN_TABLE    = "jobs_clean"
RULES_TABLE    = "association_rules"
CLUSTERS_TABLE = "job_clusters"

# Apriori parameters
MIN_SUPPORT    = 0.05   # skill pair must appear in ≥5% of listings
MIN_CONFIDENCE = 0.40   # confidence threshold
MIN_LIFT       = 1.2    # lift threshold (> 1 = non-random co-occurrence)

# K-Means parameters
K_MIN = 3
K_MAX = 8


# ── Load clean jobs ────────────────────────────────────────────────────────────
def load_clean_jobs(conn: sqlite3.Connection) -> pd.DataFrame:
    df = pd.read_sql(f"SELECT * FROM {CLEAN_TABLE}", conn)
    # Parse pipe-separated skills into lists
    df["skills_list"] = df["skills_extracted"].apply(
        lambda s: [x.strip() for x in s.split("|") if x.strip()] if isinstance(s, str) else []
    )
    # Keep only rows that have at least 1 skill
    df = df[df["skills_list"].apply(len) > 0].reset_index(drop=True)
    logger.info(f"Loaded {len(df)} skill-tagged jobs for mining")
    return df


# ── STEP 1: Association Rule Mining (Apriori) ──────────────────────────────────
def run_apriori(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the Apriori algorithm to discover frequent skill combinations.
    Returns a DataFrame of association rules sorted by lift.
    """
    try:
        from mlxtend.frequent_patterns import apriori, association_rules
        from mlxtend.preprocessing import TransactionEncoder
    except ImportError:
        logger.error("mlxtend not installed. Run: pip install mlxtend")
        return pd.DataFrame()

    logger.info("Running Apriori association rule mining...")

    transactions = df["skills_list"].tolist()

    te = TransactionEncoder()
    te_array = te.fit_transform(transactions)
    basket_df = pd.DataFrame(te_array, columns=te.columns_)

    # Mine frequent itemsets
    frequent_itemsets = apriori(
        basket_df,
        min_support=MIN_SUPPORT,
        use_colnames=True,
        max_len=3,  # pairs and triplets
    )

    if frequent_itemsets.empty:
        logger.warning("No frequent itemsets found. Try lowering MIN_SUPPORT.")
        return pd.DataFrame()

    logger.info(f"Found {len(frequent_itemsets)} frequent itemsets")

    # Generate rules
    rules = association_rules(
        frequent_itemsets,
        metric="lift",
        min_threshold=MIN_LIFT,
    )

    # Filter by confidence
    rules = rules[rules["confidence"] >= MIN_CONFIDENCE].copy()

    # Clean up for storage
    rules["antecedents"] = rules["antecedents"].apply(lambda x: " + ".join(sorted(x)))
    rules["consequents"] = rules["consequents"].apply(lambda x: " + ".join(sorted(x)))
    rules = rules.rename(columns={
        "antecedents": "if_skills",
        "consequents": "then_skills",
    })

    # Round for readability
    for col in ["support", "confidence", "lift"]:
        rules[col] = rules[col].round(3)

    rules = rules.sort_values("lift", ascending=False).reset_index(drop=True)
    logger.info(f"Generated {len(rules)} association rules (confidence ≥ {MIN_CONFIDENCE}, lift ≥ {MIN_LIFT})")
    return rules[["if_skills", "then_skills", "support", "confidence", "lift"]]


# ── STEP 2: K-Means Clustering ─────────────────────────────────────────────────
def run_kmeans(df: pd.DataFrame) -> tuple:
    """
    Vectorise job listings as binary skill features and cluster them.
    Returns (labelled_df, cluster_profiles_df).
    """
    logger.info("Running K-Means clustering on skill vectors...")

    mlb = MultiLabelBinarizer()
    X = mlb.fit_transform(df["skills_list"])
    feature_names = mlb.classes_
    logger.info(f"Feature matrix: {X.shape[0]} jobs × {X.shape[1]} skill features")

    # Elbow method to choose K
    k_chosen = _choose_k(X)
    logger.info(f"K chosen by elbow method: {k_chosen}")

    # Fit final model
    km = KMeans(n_clusters=k_chosen, random_state=42, n_init=10)
    labels = km.fit_predict(X)

    df = df.copy()
    df["cluster_id"] = labels

    # ── Label clusters as role archetypes ──────────────────────────────────────
    cluster_profiles = _build_cluster_profiles(df, X, feature_names, km, k_chosen)

    # Map cluster_id → archetype name
    label_map = cluster_profiles.set_index("cluster_id")["archetype"].to_dict()
    df["archetype"] = df["cluster_id"].map(label_map)

    return df[["raw_id", "title", "cluster_id", "archetype"]], cluster_profiles


def _choose_k(X: np.ndarray) -> int:
    """Elbow method: pick K where adding another cluster gives diminishing returns."""
    inertias = []
    k_range = range(K_MIN, min(K_MAX + 1, len(X)))
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=5)
        km.fit(X)
        inertias.append(km.inertia_)

    if len(inertias) < 3:
        return K_MIN

    # Find elbow: largest second derivative
    deltas  = [inertias[i] - inertias[i + 1] for i in range(len(inertias) - 1)]
    second  = [deltas[i] - deltas[i + 1] for i in range(len(deltas) - 1)]
    elbow_i = second.index(max(second)) + 1  # +1 because 2nd derivative is offset
    return list(k_range)[elbow_i]


# Role archetype inference rules (applied in order; first match wins).
# Rules are ordered from most specific to most general.
# Each rule requires 2+ matching skills to fire, preventing single-skill mislabelling.
ARCHETYPE_RULES = [
    # Specific stacks — require 2+ signals
    ("Mobile Developer",        ["Android", "iOS", "Flutter", "React Native", "Kotlin", "Swift", "Ionic"]),
    ("Data Scientist / ML",     ["Machine Learning", "TensorFlow", "PyTorch", "Scikit-learn", "NLP", "Deep Learning", "Computer Vision"]),
    ("Data Analyst",            ["Power BI", "Tableau", "Data Analysis", "Pandas", "Big Data", "R", "SAS"]),
    ("DevOps / Cloud Engineer", ["Docker", "Kubernetes", "AWS", "Azure", "GCP", "CI/CD", "Terraform", "Ansible", "Cloud Computing"]),
    ("Security Engineer",       ["Cybersecurity", "VPN", "Active Directory", "Firewall"]),
    ("Systems Administrator",   ["Linux", "Networking", "Bash", "Nginx", "Apache", "TCP/IP", "Monitoring", "Virtualisation", "Active Directory"]),
    ("IT Support / Sysadmin",   ["Support Technique", "Networking", "TCP/IP", "Monitoring", "Active Directory", "VPN"]),
    ("Backend Developer",       ["Django", "Flask", "Spring", "Laravel", "Node.js", "FastAPI", "NestJS", "Express.js", "API"]),
    ("Frontend Developer",      ["React", "Vue.js", "Angular", "HTML", "CSS", "Next.js", "Bootstrap", "jQuery"]),
    ("Full-Stack Developer",    ["JavaScript", "TypeScript", "SQL", "REST API", "Git", "PHP"]),
    ("Enterprise/ERP Consultant", ["SAP/ERP", "CRM", "DB2", "Oracle", "COBOL"]),
]


def _infer_archetype_scored(top_skills: list) -> str:
    """
    Score-based archetype inference: count how many keywords from each
    archetype appear in top_skills. Pick the archetype with the highest
    count (minimum 2 matches required to avoid single-skill mislabelling).
    Falls back to 'General IT' if no archetype scores >= 2.
    """
    skill_set = set(top_skills)
    scores = {}
    for archetype, keywords in ARCHETYPE_RULES:
        score = len(skill_set & set(keywords))
        if score > 0:
            scores[archetype] = score
    if not scores:
        return "General IT"
    best = max(scores, key=scores.get)
    # Require at least 2 matching signals for a confident label
    if scores[best] >= 2:
        return best
    # Only 1 signal — use it but only if it's a highly specific skill
    specific_singles = {
        "Machine Learning": "Data Scientist / ML",
        "Kubernetes": "DevOps / Cloud Engineer",
        "Flutter": "Mobile Developer",
        "React Native": "Mobile Developer",
        "Cybersecurity": "Security Engineer",
        "Power BI": "Data Analyst",
        "Tableau": "Data Analyst",
    }
    for skill in top_skills:
        if skill in specific_singles:
            return specific_singles[skill]
    return "General IT"


def _build_cluster_profiles(
    df: pd.DataFrame,
    X: np.ndarray,
    feature_names: np.ndarray,
    km: KMeans,
    k: int,
) -> pd.DataFrame:
    """
    For each cluster:
      - Find the top 10 most central skills (from cluster centroid)
      - Infer a role archetype label
    """
    profiles = []
    for cid in range(k):
        mask         = df["cluster_id"] == cid
        cluster_size = mask.sum()
        centroid     = km.cluster_centers_[cid]

        # Top skills by centroid weight
        top_idx    = np.argsort(centroid)[::-1][:10]
        top_skills = [feature_names[i] for i in top_idx if centroid[i] > 0.05]

        # Infer archetype
        archetype = _infer_archetype(top_skills)

        profiles.append({
            "cluster_id":    cid,
            "archetype":     archetype,
            "size":          int(cluster_size),
            "top_skills":    ", ".join(top_skills),
            "pct_of_total":  round(100 * cluster_size / len(df), 1),
        })

    return pd.DataFrame(profiles).sort_values("size", ascending=False).reset_index(drop=True)


def _infer_archetype(top_skills: list) -> str:
    return _infer_archetype_scored(top_skills)


# ── Main ───────────────────────────────────────────────────────────────────────
def run_mining():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("=== Phase 3: Association Rule Mining + K-Means Clustering ===")

    conn = sqlite3.connect(DB_PATH)

      # Verify clean data exists
    try:
        df = load_clean_jobs(conn)
    except Exception as e:
        logger.error(f"Could not load clean jobs: {e}. Run pipeline/cleaner.py first.")
        conn.close()
        return

    exports = DATA_DIR / "exports"
    exports.mkdir(parents=True, exist_ok=True)

    # Guard: need enough skilled jobs for meaningful mining
    skilled_count = df["skills_list"].apply(len).gt(0).sum()
    if skilled_count < K_MIN:
        logger.warning(
            f"Only {skilled_count} jobs have extracted skills (need >= {K_MIN}). "
            f"Mining skipped. Run scrapers to populate the DB with real job data."
        )
        conn.close()
        return

    # -- Association rules
    rules_df = run_apriori(df)
    if not rules_df.empty:
        rules_df.to_sql(RULES_TABLE, conn, if_exists="replace", index=False)
        rules_df.to_csv(exports / "association_rules.csv", index=False, encoding="utf-8-sig")
        logger.info(f"Saved {len(rules_df)} rules to DB and CSV")
    else:
        logger.warning("No rules generated - check data volume and MIN_SUPPORT setting")

    # -- K-Means clustering (guarded against empty feature matrix)
    try:
        clusters_df, profiles_df = run_kmeans(df)
        clusters_df.to_sql(CLUSTERS_TABLE, conn, if_exists="replace", index=False)
        clusters_df.to_csv(exports / "job_clusters.csv", index=False, encoding="utf-8-sig")
        profiles_df.to_csv(exports / "cluster_profiles.csv", index=False, encoding="utf-8-sig")
        logger.info(f"Saved cluster assignments and profiles to DB and CSV")
    except ValueError as e:
        logger.warning(f"K-Means skipped: {e}")

    conn.close()

    # ── Summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  PHASE 3 COMPLETE — Mining Results")
    print("=" * 60)

    print(f"\n  Association Rules (top 15 by lift):")
    print(f"  {'Antecedent':<30} {'Consequent':<22} {'Conf':>6} {'Lift':>6}")
    print(f"  {'-'*30} {'-'*22} {'-'*6} {'-'*6}")
    for _, r in rules_df.head(15).iterrows():
        print(f"  {r['if_skills']:<30} → {r['then_skills']:<22} {r['confidence']:>6.2f} {r['lift']:>6.2f}")

    print(f"\n  K-Means Cluster Profiles:")
    print(f"  {'#':<4} {'Archetype':<28} {'Size':>5} {'%':>5} {'Top Skills'}")
    print(f"  {'-'*4} {'-'*28} {'-'*5} {'-'*5} {'-'*30}")
    for _, p in profiles_df.iterrows():
        skills_short = ", ".join(p["top_skills"].split(", ")[:4])
        print(f"  {p['cluster_id']:<4} {p['archetype']:<28} {p['size']:>5} {p['pct_of_total']:>4.0f}%  {skills_short}")

    print(f"\n  Exports: {exports}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_mining()
