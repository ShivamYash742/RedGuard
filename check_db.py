import sqlite3
conn = sqlite3.connect("backend/dev.db")
c = conn.cursor()
c.execute("SELECT promptText, responseExcerpt, status FROM ProbeEvent WHERE status='ALLOWED' LIMIT 5")
for row in c.fetchall():
    print(row)
