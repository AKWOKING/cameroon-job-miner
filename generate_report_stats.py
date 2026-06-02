"""
generate_report_stats.py
------------------------
Generates comprehensive statistics for the data mining report.
"""

import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH = Path(r"C:\Users\JA 12\Documents\lvl 400\Second Semester\Data mining 2026\cameroon-job-miner-complete\cameroon-job-miner-final\data\jobs.db")
EXPORTS_DIR = Path(r"C:\Users\JA 12\Documents\lvl 400\Second Semester\Data mining 2026\cameroon-job-miner-complete\cameroon-job-miner-final\data\exports")

conn = sqlite3.connect(DB_PATH)

print("=" * 70)
print("CAMEROON JOB MINER - DATA MINING REPORT STATISTICS")
print("=" * 70)

# ============= SECTION 1: DATA COLLECTION STATISTICS =============
print("\n" + "=" * 70)
print("SECTION 1: DATA COLLECTION STATISTICS")
print("=" * 70)

query = """
SELECT portal, COUNT(*) as count
FROM jobs
GROUP BY portal
ORDER BY count DESC
"""
portal_stats = pd.read_sql(query, conn)
print("\nJobs by Portal:")
for _, row in portal_stats.iterrows():
    print(f"  {row['portal']}: {row['count']} jobs")

total_jobs = portal_stats['count'].sum()
print(f"\nTotal raw jobs in database: {total_jobs}")

# ============= SECTION 2: DATA CLEANING STATISTICS =============
print("\n" + "=" * 70)
print("SECTION 2: DATA CLEANING STATISTICS")
print("=" * 70)

clean_count = pd.read_sql("SELECT COUNT(*) as count FROM jobs_clean", conn)
print(f"\nJobs after cleaning (with skills): {clean_count['count'].iloc[0]}")

# Get language distribution
lang_query = """
SELECT language, COUNT(*) as count
FROM jobs_clean
GROUP BY language
ORDER BY count DESC
"""
lang_stats = pd.read_sql(lang_query, conn)
print("\nLanguage Distribution:")
for _, row in lang_stats.iterrows():
    pct = (row['count'] / clean_count['count'].iloc[0]) * 100
    print(f"  {row['language']}: {row['count']} ({pct:.1f}%)")

# City distribution
city_query = """
SELECT city, COUNT(*) as count
FROM jobs_clean
GROUP BY city
ORDER BY count DESC
LIMIT 10
"""
city_stats = pd.read_sql(city_query, conn)
print("\nTop 10 Cities:")
for _, row in city_stats.iterrows():
    pct = (row['count'] / clean_count['count'].iloc[0]) * 100
    print(f"  {row['city']}: {row['count']} ({pct:.1f}%)")

# Experience distribution
exp_query = """
SELECT experience_level, COUNT(*) as count
FROM jobs_clean
GROUP BY experience_level
ORDER BY count DESC
"""
exp_stats = pd.read_sql(exp_query, conn)
print("\nExperience Level Distribution:")
for _, row in exp_stats.iterrows():
    pct = (row['count'] / clean_count['count'].iloc[0]) * 100
    print(f"  {row['experience_level']}: {row['count']} ({pct:.1f}%)")

# ============= SECTION 3: SKILL EXTRACTION STATISTICS =============
print("\n" + "=" * 70)
print("SECTION 3: SKILL EXTRACTION STATISTICS")
print("=" * 70)

# Load taxonomy
taxonomy_path = Path(r"C:\Users\JA 12\Documents\lvl 400\Second Semester\Data mining 2026\cameroon-job-miner-complete\cameroon-job-miner-final\data\skill_taxonomy.csv")
if taxonomy_path.exists():
    taxonomy = pd.read_csv(taxonomy_path)
    print(f"\nSkill Taxonomy:")
    print(f"  Total alias entries: {len(taxonomy)}")
    print(f"  Unique canonical skills: {taxonomy['canonical_skill'].nunique()}")

# Skill frequency
freq_path = EXPORTS_DIR / "skill_frequency.csv"
if freq_path.exists():
    freq_df = pd.read_csv(freq_path)
    print(f"\nTotal unique skills found: {len(freq_df)}")
    print(f"\nTop 30 Skills by Frequency:")
    print(f"  {'Rank':<5} {'Skill':<25} {'Count':>6} {'%':>6}")
    print(f"  {'-'*5} {'-'*25} {'-'*6} {'-'*6}")
    for idx, row in freq_df.head(30).iterrows():
        print(f"  {idx+1:<5} {row['skill']:<25} {row['count']:>6} {row['pct']:>5.1f}%")

# Average skills per job
avg_skills = pd.read_sql("SELECT AVG(LENGTH(skills_extracted) - LENGTH(REPLACE(skills_extracted, '|', '')) + 1) as avg FROM jobs_clean WHERE skills_extracted != ''", conn)
print(f"\nAverage skills per job: {avg_skills['avg'].iloc[0]:.2f}")

# ============= SECTION 4: ASSOCIATION RULES STATISTICS =============
print("\n" + "=" * 70)
print("SECTION 4: ASSOCIATION RULES STATISTICS")
print("=" * 70)

rules_query = "SELECT * FROM association_rules ORDER BY lift DESC LIMIT 20"
rules_df = pd.read_sql(rules_query, conn)

print(f"\nTotal association rules generated: {len(pd.read_sql('SELECT * FROM association_rules', conn))}")
print(f"\nTop 20 Association Rules (sorted by Lift):")
print(f"  {'Antecedent':<30} → {'Consequent':<22} {'Conf':>6} {'Lift':>6}")
print(f"  {'-'*30}   {'-'*22}   {'-'*6} {'-'*6}")
for _, r in rules_df.iterrows():
    print(f"  {r['if_skills']:<30} → {r['then_skills']:<22} {r['confidence']:>6.2f} {r['lift']:>6.2f}")

# Rule statistics
rules_full = pd.read_sql("SELECT * FROM association_rules", conn)
print(f"\nAssociation Rule Statistics:")
print(f"  Average support: {rules_full['support'].mean():.4f}")
print(f"  Average confidence: {rules_full['confidence'].mean():.4f}")
print(f"  Average lift: {rules_full['lift'].mean():.4f}")
print(f"  Max lift: {rules_full['lift'].max():.2f}")
print(f"  Min support threshold: 0.05 (5%)")
print(f"  Min confidence threshold: 0.40 (40%)")
print(f"  Min lift threshold: 1.2")

# ============= SECTION 5: K-MEANS CLUSTERING STATISTICS =============
print("\n" + "=" * 70)
print("SECTION 5: K-MEANS CLUSTERING STATISTICS")
print("=" * 70)

# Load cluster profiles
profiles_path = EXPORTS_DIR / "cluster_profiles.csv"
if profiles_path.exists():
    profiles_df = pd.read_csv(profiles_path)
    print(f"\nK-Means Cluster Profiles:")
    print(f"  Number of clusters (K): {len(profiles_df)}")
    print(f"  Method: Elbow (tested K from 3 to 8)")
    print()
    print(f"  {'Cluster':<8} {'Archetype':<30} {'Jobs':>5} {'%':>5} {'Top Skills'}")
    print(f"  {'-'*8} {'-'*30} {'-'*5} {'-'*5} {'-'*35}")
    for _, row in profiles_df.iterrows():
        top_skills = ", ".join(str(row['top_skills']).split(", ")[:4])
        print(f"  {row['cluster_id']:<8} {row['archetype']:<30} {row['size']:>5} {row['pct_of_total']:>4.0f}%  {top_skills}")

# Load job clusters
clusters_path = EXPORTS_DIR / "job_clusters.csv"
if clusters_path.exists():
    job_clusters = pd.read_csv(clusters_path)
    print(f"\nTotal jobs clustered: {len(job_clusters)}")

# ============= SECTION 6: PORTAL COMPARISON =============
print("\n" + "=" * 70)
print("SECTION 6: PORTAL COMPARISON")
print("=" * 70)

portal_detail = """
SELECT
    portal,
    COUNT(*) as total_jobs,
    AVG(LENGTH(skills_extracted) - LENGTH(REPLACE(skills_extracted, '|', '')) + 1) as avg_skills,
    COUNT(DISTINCT city) as unique_cities
FROM jobs_clean jc
JOIN jobs j ON jc.id = j.id
WHERE jc.skills_extracted != ''
GROUP BY portal
ORDER BY total_jobs DESC
"""
portal_comparison = pd.read_sql(portal_detail, conn)
print("\nPortal Comparison (jobs with skills):")
print(f"  {'Portal':<15} {'Total Jobs':>12} {'Avg Skills':>12} {'Unique Cities':>15}")
print(f"  {'-'*15} {'-'*12} {'-'*12} {'-'*15}")
for _, row in portal_comparison.iterrows():
    print(f"  {row['portal']:<15} {row['total_jobs']:>12} {row['avg_skills']:>12.2f} {row['unique_cities']:>15}")

# ============= SECTION 7: SKILL CATEGORIES =============
print("\n" + "=" * 70)
print("SECTION 7: SKILL CATEGORY ANALYSIS")
print("=" * 70)

# Categorize skills manually for the report
programming_langs = ['Java', 'JavaScript', 'Python', 'SQL', 'TypeScript', 'PHP', 'C#', 'Ruby', 'Go', 'R', 'Scala']
frameworks = ['React', 'Node.js', 'Django', 'Laravel', 'Spring', 'Angular', 'Vue.js', 'Flask', 'Express']
databases = ['MySQL', 'PostgreSQL', 'MongoDB', 'Oracle', 'Redis', 'SQL Server']
devops = ['Docker', 'Kubernetes', 'CI/CD', 'AWS', 'Azure', 'Git', 'Jenkins', 'Terraform']
soft_skills = ['Agile', 'Scrum', 'Communication', 'Leadership', 'Team Management']
other = ['SAP/ERP', 'CRM', 'Monitoring', 'Networking', 'Support Technique']

categories = {
    'Programming Languages': programming_langs,
    'Frameworks/Libraries': frameworks,
    'Databases': databases,
    'DevOps/Cloud': devops,
    'Soft Skills/Methodologies': soft_skills,
}

print("\nSkills by Category (from top 30):")
for cat_name, skill_list in categories.items():
    matching = freq_df[freq_df['skill'].isin(skill_list)]
    if len(matching) > 0:
        total_count = matching['count'].sum()
        print(f"\n  {cat_name}:")
        for _, row in matching.iterrows():
            print(f"    {row['skill']}: {row['count']} ({row['pct']:.1f}%)")
        print(f"    → Category total: {total_count} skill mentions")

conn.close()

print("\n" + "=" * 70)
print("END OF STATISTICS REPORT")
print("=" * 70)