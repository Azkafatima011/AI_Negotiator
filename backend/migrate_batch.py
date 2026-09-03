"""One-shot migration: add batch support to SQLite DB."""
import sqlite3

conn = sqlite3.connect("negotiation.db")
cur = conn.cursor()

# 1. Add batch_id FK column to negotiations
cols = [row[1] for row in cur.execute("PRAGMA table_info(negotiations)").fetchall()]
if "batch_id" not in cols:
    cur.execute("ALTER TABLE negotiations ADD COLUMN batch_id TEXT")
    print("Added batch_id to negotiations")
else:
    print("batch_id already present")

# 2. Create negotiation_batches table
cur.execute("""
CREATE TABLE IF NOT EXISTS negotiation_batches (
    id                  TEXT PRIMARY KEY,
    commodity           TEXT NOT NULL,
    quantity            REAL NOT NULL,
    unit                TEXT DEFAULT 'kg',
    currency            TEXT DEFAULT 'PKR',
    status              TEXT DEFAULT 'RUNNING',
    best_negotiation_id TEXT,
    organization_id     TEXT,
    created_at          DATETIME
)
""")
print("negotiation_batches table ready")

conn.commit()
conn.close()
print("Migration complete.")
