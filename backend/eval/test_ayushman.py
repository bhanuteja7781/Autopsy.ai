import asyncio
from backend.api.main import run_full_investigation_pipeline
from backend.core.db import db

async def test():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM entities WHERE name LIKE '%Ayushman%'")
    ent = cur.fetchone()
    conn.close()
    
    print("Testing investigation for:", ent["name"], ent["id"])
    await run_full_investigation_pipeline(ent["id"], ent["name"])
    
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.verdict, c.confidence, ca.raw_excerpt as a, cb.raw_excerpt as b
        FROM comparisons c
        JOIN claims ca ON c.claim_a_id = ca.id
        JOIN claims cb ON c.claim_b_id = cb.id
        WHERE c.entity_id = ?
    """, (ent["id"],))
    comps = cur.fetchall()
    print("Ayushman Comparisons in DB:", len(comps))
    for c in comps:
        print("  *", c["verdict"], "| Earlier:", c["a"][:40], "vs Later:", c["b"][:40])
    conn.close()

if __name__ == "__main__":
    asyncio.run(test())
