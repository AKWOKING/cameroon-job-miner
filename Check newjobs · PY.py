import sqlite3

c = sqlite3.connect('data/jobs.db')

count = c.execute("SELECT COUNT(*) FROM jobs WHERE source='newjobscm'").fetchone()[0]
print(f"newjobscm unique jobs: {count}")

print("\nSample titles and URLs:")
for r in c.execute("SELECT title, url FROM jobs WHERE source='newjobscm' LIMIT 10").fetchall():
    print(f"  {r[0]} | {r[1]}")

print("\nAll sources in DB:")
for r in c.execute("SELECT source, COUNT(*) FROM jobs GROUP BY source").fetchall():
    print(f"  {r[0]}: {r[1]}")

c.close()