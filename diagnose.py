import sqlite3

c = sqlite3.connect('data/jobs.db')

print("=== JOBS WITH ZERO SKILLS (first 5) ===")
rows = c.execute("""
    SELECT j.title, j.skills_raw, substr(j.description,1,300)
    FROM jobs j
    WHERE j.url NOT LIKE '%demo.example.com%'
    AND j.id IN (
        SELECT raw_id FROM jobs_clean
        WHERE skill_count = 0
        LIMIT 5
    )
""").fetchall()

for r in rows:
    print("TITLE     :", r[0])
    print("SKILLS_RAW:", r[1])
    print("DESC      :", r[2])
    print("---")

print("\n=== SCALA CHECK — sample jobs where Scala matched ===")
rows2 = c.execute("""
    SELECT j.title, substr(j.description,1,400)
    FROM jobs j
    JOIN jobs_clean jc ON j.id = jc.raw_id
    WHERE jc.skills_extracted LIKE '%Scala%'
    LIMIT 3
""").fetchall()

for r in rows2:
    print("TITLE:", r[0])
    print("DESC :", r[1])
    print("---")

c.close()
