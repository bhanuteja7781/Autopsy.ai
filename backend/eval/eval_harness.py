from __future__ import annotations
import asyncio
import logging
import uuid
import datetime
from dataclasses import dataclass
from typing import List, Dict, Any, Optional

from backend.core.db import db
from backend.engine.drift_reasoning_engine import DriftReasoningEngine, REASONER_MODEL_VERSION
from backend.engine.extractor_engine import EXTRACTOR_MODEL_VERSION

logger = logging.getLogger("eval_harness")
REGRESSION_TOLERANCE = 0.03  # max allowed accuracy drop vs last promoted run

@dataclass
class EvalCase:
    id: str
    claim_a_excerpt: str
    claim_b_excerpt: str
    claim_type: str
    human_label: str

@dataclass
class EvalRunResult:
    total_cases: int
    accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    per_case_results: list[dict]

class EvalHarness:
    def __init__(self, reasoning_engine: Optional[DriftReasoningEngine] = None):
        self.engine = reasoning_engine or DriftReasoningEngine()
        self.extractor_model_version = EXTRACTOR_MODEL_VERSION
        self.reasoner_model_version = REASONER_MODEL_VERSION
        self.prompt_version_hash = "hash_v1_dpr_release"

    async def load_cases(self) -> list[EvalCase]:
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT id, claim_a_excerpt, claim_b_excerpt, claim_type, human_label FROM eval_cases")
        rows = cur.fetchall()
        conn.close()

        if not rows:
            from backend.eval.eval_cases_seed import seed_eval_cases
            seed_eval_cases()
            conn = db.get_connection()
            cur = conn.cursor()
            cur.execute("SELECT id, claim_a_excerpt, claim_b_excerpt, claim_type, human_label FROM eval_cases")
            rows = cur.fetchall()
            conn.close()

        return [
            EvalCase(
                id=r["id"],
                claim_a_excerpt=r["claim_a_excerpt"],
                claim_b_excerpt=r["claim_b_excerpt"],
                claim_type=r["claim_type"],
                human_label=r["human_label"]
            )
            for r in rows
        ]

    async def run(self) -> EvalRunResult:
        cases = await self.load_cases()
        results = []
        correct = 0
        false_positives = 0
        false_negatives = 0
        contradiction_negative_pool = 0
        contradiction_positive_pool = 0

        for case in cases:
            model_output = await self.engine.compare_raw_excerpts(
                case.claim_a_excerpt, case.claim_b_excerpt, case.claim_type
            )
            is_correct = model_output.verdict == case.human_label
            if is_correct:
                correct += 1

            if case.human_label != "silent_contradiction":
                contradiction_negative_pool += 1
                if model_output.verdict == "silent_contradiction":
                    false_positives += 1
            if case.human_label == "silent_contradiction":
                contradiction_positive_pool += 1
                if model_output.verdict != "silent_contradiction":
                    false_negatives += 1

            results.append({
                "eval_case_id": case.id,
                "claim_a_excerpt": case.claim_a_excerpt,
                "claim_b_excerpt": case.claim_b_excerpt,
                "claim_type": case.claim_type,
                "human_label": case.human_label,
                "model_label": model_output.verdict,
                "model_confidence": model_output.calibrated_confidence,
                "model_reasoning": model_output.reasoning,
                "correct": is_correct,
            })

        accuracy = correct / len(cases) if cases else 0.0
        fpr = false_positives / contradiction_negative_pool if contradiction_negative_pool else 0.0
        fnr = false_negatives / contradiction_positive_pool if contradiction_positive_pool else 0.0

        return EvalRunResult(
            total_cases=len(cases),
            accuracy=round(accuracy, 4),
            false_positive_rate=round(fpr, 4),
            false_negative_rate=round(fnr, 4),
            per_case_results=results,
        )

    async def persist_and_gate(self, result: EvalRunResult) -> bool:
        conn = db.get_connection()
        cur = conn.cursor()

        cur.execute("SELECT accuracy FROM eval_runs WHERE promoted_to_production = 1 ORDER BY run_at DESC LIMIT 1")
        last_promoted = cur.fetchone()
        baseline_accuracy = last_promoted["accuracy"] if last_promoted else 0.80
        promote = result.accuracy >= (baseline_accuracy - REGRESSION_TOLERANCE)

        run_id = str(uuid.uuid4())
        cur.execute("""
        INSERT INTO eval_runs
            (id, run_at, extractor_model_version, reasoner_model_version, prompt_version_hash,
             total_cases, accuracy, false_positive_rate, false_negative_rate, promoted_to_production)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            run_id, datetime.datetime.utcnow().isoformat(),
            self.extractor_model_version, self.reasoner_model_version, self.prompt_version_hash,
            result.total_cases, result.accuracy, result.false_positive_rate, result.false_negative_rate,
            1 if promote else 0
        ))

        for r in result.per_case_results:
            cur.execute("""
            INSERT OR REPLACE INTO eval_case_results (id, eval_run_id, eval_case_id, model_label, model_confidence, correct)
            VALUES (?, ?, ?, ?, ?, ?)
            """, (
                str(uuid.uuid4()), run_id, r["eval_case_id"],
                r["model_label"], r["model_confidence"], 1 if r["correct"] else 0
            ))

        conn.commit()
        conn.close()

        return promote

if __name__ == "__main__":
    harness = EvalHarness()
    res = asyncio.run(harness.run())
    promoted = asyncio.run(harness.persist_and_gate(res))
    print(f"Eval Run: {res.total_cases} cases | Accuracy: {res.accuracy*100:.1f}% | Promoted: {promoted}")
