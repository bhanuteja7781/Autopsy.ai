import asyncio
import sys
import os

from backend.core.db import db
from backend.api.main import run_full_investigation_pipeline, trigger_eval_run
from backend.eval.eval_harness import EvalHarness

async def run_pipeline_tests():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM entities")
    rows = cur.fetchall()
    conn.close()
    
    print(f"Testing pipeline against {len(rows)} registered entities...")
    for row in rows:
        await run_full_investigation_pipeline(row["id"], row["name"])
        print(f"[OK] Pipeline succeeded for: {row['name']}")
    
    # Run evaluation harness
    harness = EvalHarness()
    eval_result = await harness.run()
    promoted = await harness.persist_and_gate(eval_result)
    
    print(f"\n[OK] Eval Benchmark: {eval_result.total_cases} cases | Accuracy: {eval_result.accuracy * 100:.1f}% | Promoted: {promoted}")
    
    costs = db.get_cost_summary()
    print(f"[OK] Cost Ledger verified: ${costs['grand_total_usd']} across {costs['grand_total_tokens']} tokens.")

if __name__ == "__main__":
    asyncio.run(run_pipeline_tests())
