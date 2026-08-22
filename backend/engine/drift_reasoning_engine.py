from __future__ import annotations
import json
import logging
import uuid
import datetime
import re
from dataclasses import dataclass
from typing import Optional, Dict

from backend.core.db import db
from backend.core.llm_client import llm_client
from backend.core.config import settings

logger = logging.getLogger("drift_reasoning_engine")

REASONER_MODEL_VERSION = f"reasoner-v2-{settings.REASONER_MODEL}"
HUMAN_REVIEW_CONFIDENCE_THRESHOLD = 0.60
SILENT_CONTRADICTION_MIN_SURFACE_CONFIDENCE = 0.60

REASONING_SYSTEM_PROMPT = """You are a forensic policy analyst comparing two official statements about the same policy, made at different points in time.

Claim A is strictly the EARLIER official release. Claim B is strictly the LATER official release. Analyze how Claim B alters, modifies, or silently shifts the operative terms established in Claim A.

Classify their relationship and return ONLY a JSON object:
{
  "verdict": "explicit_update" | "silent_contradiction" | "insufficient_evidence",
  "confidence": 0.0-1.0,
  "reasoning": "<forensic explanation — see required format below>"
}

Verdict definitions:
- explicit_update: the claims differ substantively AND the later source explicitly signals a change (e.g., 'revised', 'amended', 'effective from', 'supersedes', 'expanded to', 'cabinet approved').
- silent_contradiction: the claims differ in substance but the later source gives NO indication anything changed — the prior rule is silently overwritten.
- insufficient_evidence: the excerpts are too ambiguous, trivial, or unrelated to classify confidently.

CRITICAL SUBSTANTIVE DRIFT RULES:
- Discard trivial procedural differences (e.g., date of bill passage vs. date of presidential assent, gazette volume numbers, printing press locations).
- Focus EXCLUSIVELY on changes to rights, obligations, exemptions, eligibility cutoffs, or behavioral rules.
- If the claims only differ in procedural publication dates with no change to the actual rule, return verdict "insufficient_evidence" with confidence 0.0.

DO NOT use verdict 'consistent' — pairs with >90% text similarity are pre-filtered upstream and never reach you.

MANDATORY REASONING FORMAT — your `reasoning` field MUST follow all 3 parts, in order, in a single paragraph:
1. THE SHIFT: State the exact number, date, eligibility term, or access rule that changed between Claim A and Claim B. Quote specific figures or phrases from both claims.
2. THE MECHANISM: State explicitly whether the later document cited, referenced, or acknowledged the change from the earlier rule — or whether it silently introduced a different rule with no cross-reference.
3. IMPACT SUMMARY: One sentence on what this concretely means for the affected beneficiary, user, or party.

NEVER output generic phrases like 'statements appear broadly compatible' or 'high semantic overlap.' Every reasoning must reference specific clause language from both excerpts."""

REASONING_SYSTEM_PROMPT += """

VALIDATION & DOMAIN CHECK:
Verify that Claim A and Claim B refer to the same statutory subject or policy topic.
Only if the claims describe completely unrelated subjects or foreign entities with no connection should you return verdict "insufficient_evidence" with confidence 0.0."""


def pair_and_sort_claims(claims: list[dict]) -> tuple[Optional[dict], Optional[dict]]:
    """Sort claims by true document publication/effective/created date ascending and return earliest and latest."""
    if not claims or len(claims) < 2:
        return None, None
    sorted_claims = sorted(
        claims,
        key=lambda x: (x.get('effective_date') or x.get('published_at') or x.get('created_at') or '1970-01-01')
    )
    claim_a = sorted_claims[0]
    claim_b = sorted_claims[-1]
    return claim_a, claim_b


@dataclass
class ClaimForComparison:
    claim_id: str
    raw_excerpt: str
    normalized_value: dict
    published_at: Optional[str]
    source_url: str
    effective_date: Optional[str] = None


@dataclass
class ComparisonResult:
    id: str
    claim_a_id: str
    claim_b_id: str
    verdict: str
    raw_confidence: float
    calibrated_confidence: float
    reasoning: str
    requires_human_review: bool
    reasoner_model_version: str = REASONER_MODEL_VERSION


class ConfidenceCalibrator:
    """Adjusts raw model confidence against empirical accuracy curve from eval runs."""

    def __init__(self, calibration_curve: Optional[Dict[str, float]] = None):
        self.curve = calibration_curve or {
            "0.0-0.5": 0.52,
            "0.5-0.6": 0.61,
            "0.6-0.7": 0.74,
            "0.7-0.8": 0.83,
            "0.8-0.9": 0.91,
            "0.9-1.0": 0.96,
        }

    def calibrate(self, raw_confidence: float) -> float:
        bucket = self._bucket_for(raw_confidence)
        observed_accuracy = self.curve.get(bucket, raw_confidence)
        return round((raw_confidence + observed_accuracy) / 2, 3)

    @staticmethod
    def _bucket_for(confidence: float) -> str:
        lower = int(confidence * 10) / 10
        upper = round(lower + 0.1, 1)
        return f"{lower}-{upper}"


class DriftReasoningEngine:
    def __init__(self, calibrator: Optional[ConfidenceCalibrator] = None):
        self.calibrator = calibrator or ConfidenceCalibrator()

    def build_comparison_pairs(
        self, claims: list[ClaimForComparison]
    ) -> list[tuple[ClaimForComparison, ClaimForComparison]]:
        """
        Adjacent-pair (catches step-by-step drift) AND Baseline-pair
        (catches cumulative multi-year drift). O(n) complexity.
        """
        sorted_claims = sorted(claims, key=self._claim_date)
        pairs: list[tuple[ClaimForComparison, ClaimForComparison]] = []

        if len(sorted_claims) < 2:
            return []

        # 1. Adjacent pairs
        for i in range(1, len(sorted_claims)):
            pairs.append((sorted_claims[i - 1], sorted_claims[i]))

        # 2. Baseline pairs against the earliest claim
        if len(sorted_claims) > 2:
            baseline = sorted_claims[0]
            for later in sorted_claims[2:]:
                pairs.append((baseline, later))

        return pairs

    @staticmethod
    def _claim_date(claim: ClaimForComparison) -> datetime.date:
        """Return the governing policy date, falling back to publication date."""
        candidates = [claim.effective_date, claim.published_at]
        for value in candidates:
            if not value:
                continue
            match = re.search(r"\d{4}[-/]\d{2}[-/]\d{2}", str(value))
            if match:
                try:
                    return datetime.date.fromisoformat(match.group(0).replace("/", "-"))
                except ValueError:
                    continue
        return datetime.date.max

    async def compare_raw_excerpts(
        self, excerpt_a: str, excerpt_b: str, claim_type: str = "general"
    ) -> ComparisonResult:
        """Helper for eval harness to directly compare two raw excerpts."""
        dummy_a = ClaimForComparison(
            claim_id="eval_a",
            raw_excerpt=excerpt_a,
            normalized_value={},
            published_at="2020-01-01",
            source_url="eval_source_a",
        )
        dummy_b = ClaimForComparison(
            claim_id="eval_b",
            raw_excerpt=excerpt_b,
            normalized_value={},
            published_at="2022-01-01",
            source_url="eval_source_b",
        )
        return await self.compare(dummy_a, dummy_b)

    async def compare(
        self, claim_a: ClaimForComparison, claim_b: ClaimForComparison
    ) -> ComparisonResult:
        """
        Calls Model 2 (OpenRouter / GPT family) exclusively.
        Raises RuntimeError if the LLM call fails or returns unparseable output,
        so the pipeline surfaces an explicit HTTP 500.
        """
        # Enforce ordering here as well as during pair construction so callers
        # cannot accidentally send a newer document as Claim A.
        if self._claim_date(claim_b) < self._claim_date(claim_a):
            claim_a, claim_b = claim_b, claim_a

        prompt_payload = {
            "claim_a": {
                "excerpt": claim_a.raw_excerpt,
                "effective_date": claim_a.effective_date,
                "date": claim_a.published_at,
                "source": claim_a.source_url,
            },
            "claim_b": {
                "excerpt": claim_b.raw_excerpt,
                "effective_date": claim_b.effective_date,
                "date": claim_b.published_at,
                "source": claim_b.source_url,
            },
        }

        # ── Call Model 2: OpenRouter / GPT-family Reasoner ────────────────
        response_text = llm_client.get_reasoning_model().generate(
            prompt=json.dumps(prompt_payload),
            system_instruction=REASONING_SYSTEM_PROMPT,
            model=settings.REASONER_MODEL,
        )

        if not response_text:
            raise RuntimeError(
                f"Model 2 ({settings.REASONER_MODEL}) returned empty response. "
                "Check OpenRouter API key, model name, and quota."
            )

        # Parse JSON response
        try:
            from backend.core.llm_client import extract_json_object_str
            clean_json = extract_json_object_str(response_text) or response_text
            parsed = json.loads(clean_json)
        except json.JSONDecodeError as e:
            raise RuntimeError(
                f"Model 2 returned non-JSON output: {e}. Raw response: {response_text[:300]}"
            )

        verdict = parsed.get("verdict", "")
        if "confidence" not in parsed or "reasoning" not in parsed:
            raise RuntimeError("Model 2 response must include confidence and reasoning.")
        raw_confidence = float(parsed["confidence"])
        reasoning = parsed["reasoning"]
        if not 0.0 <= raw_confidence <= 1.0:
            raise RuntimeError(f"Model 2 returned confidence outside 0.0-1.0: {raw_confidence}")

        valid_verdicts = {"explicit_update", "silent_contradiction", "insufficient_evidence"}
        if verdict not in valid_verdicts:
            raise RuntimeError(
                f"Model 2 returned invalid verdict '{verdict}'. "
                f"Expected one of {valid_verdicts}."
            )

        if not reasoning or len(reasoning.strip()) < 20:
            raise RuntimeError(
                "Model 2 returned empty or trivially short reasoning. "
                "The model may be misconfigured or the prompt was rejected."
            )

        calibrated = self.calibrator.calibrate(raw_confidence)

        requires_review = calibrated < HUMAN_REVIEW_CONFIDENCE_THRESHOLD or (
            verdict == "silent_contradiction"
            and calibrated < SILENT_CONTRADICTION_MIN_SURFACE_CONFIDENCE
        )

        logger.info(
            "Comparison result: verdict=%s calibrated_conf=%.3f requires_review=%s",
            verdict,
            calibrated,
            requires_review,
        )

        return ComparisonResult(
            id=str(uuid.uuid4()),
            claim_a_id=claim_a.claim_id,
            claim_b_id=claim_b.claim_id,
            verdict=verdict,
            raw_confidence=raw_confidence,
            calibrated_confidence=calibrated,
            reasoning=reasoning,
            requires_human_review=requires_review,
            reasoner_model_version=settings.REASONER_MODEL,
        )

    @staticmethod
    def _is_duplicate_pair(
        claim_a: ClaimForComparison, claim_b: ClaimForComparison
    ) -> bool:
        """Returns True if the pair is duplicate noise and should be dropped."""
        import difflib

        # Near-identical text guard (>90% character similarity)
        ratio = difflib.SequenceMatcher(
            None,
            claim_a.raw_excerpt.lower().strip(),
            claim_b.raw_excerpt.lower().strip(),
        ).ratio()
        if ratio >= 0.90:
            logger.debug(
                "No-op: %.0f%% text similarity for claim_a=%s claim_b=%s — dropped.",
                ratio * 100,
                claim_a.claim_id,
                claim_b.claim_id,
            )
            return True
        return False

    async def run_pipeline_for_entity(
        self, entity_id: str
    ) -> list[ComparisonResult]:
        """Runs pairing, reasoning, and persistence across all claims for an entity."""
        conn = db.get_connection()
        cur = conn.cursor()

        cur.execute(
            """
            SELECT c.id, c.raw_excerpt, c.normalized_value, c.effective_date, d.published_at, d.source_url
            FROM claims c
            JOIN documents d ON c.document_id = d.id
            WHERE d.entity_id = ?
            ORDER BY COALESCE(c.effective_date, d.published_at) ASC
            """,
            (entity_id,),
        )
        rows = cur.fetchall()

        claims = [
            ClaimForComparison(
                claim_id=r["id"],
                raw_excerpt=r["raw_excerpt"],
                normalized_value=(
                    json.loads(r["normalized_value"]) if r["normalized_value"] else {}
                ),
                published_at=r["published_at"],
                source_url=r["source_url"],
                effective_date=(
                    r["effective_date"]
                    or (json.loads(r["normalized_value"]).get("effective_date") if r["normalized_value"] else None)
                ),
            )
            for r in rows
        ]

        pairs = self.build_comparison_pairs(claims)
        comparisons: list[ComparisonResult] = []
        dropped_count = 0

        for claim_a, claim_b in pairs:
            if self._is_duplicate_pair(claim_a, claim_b):
                dropped_count += 1
                continue

            # Let compare() raise — caught in run_full_investigation_pipeline → HTTP 500
            res = await self.compare(claim_a, claim_b)
            comparisons.append(res)

            cur.execute(
                """
                INSERT OR REPLACE INTO comparisons
                (id, entity_id, claim_a_id, claim_b_id, verdict, confidence, reasoning,
                 requires_human_review, reasoner_model_version, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    res.id,
                    entity_id,
                    res.claim_a_id,
                    res.claim_b_id,
                    res.verdict,
                    res.calibrated_confidence,
                    res.reasoning,
                    1 if res.requires_human_review else 0,
                    res.reasoner_model_version,
                    datetime.datetime.utcnow().isoformat(),
                ),
            )

        conn.commit()
        conn.close()

        # Log cost & audit trail
        tok_in = len(pairs) * 180
        tok_out = len(pairs) * 60
        cost_usd = round((tok_in + tok_out) * 0.000004, 4)
        db.log_cost(
            entity_id, "reasoning", tokens_in=tok_in, tokens_out=tok_out, cost_usd=cost_usd
        )
        db.log_audit(
            "system",
            None,
            "reasoning_completed",
            "comparisons",
            entity_id,
            {
                "comparisons_count": len(comparisons),
                "duplicate_pairs_dropped": dropped_count,
            },
        )

        silent_count = sum(1 for c in comparisons if c.verdict == "silent_contradiction")
        explicit_count = sum(1 for c in comparisons if c.verdict == "explicit_update")
        print(
            f"[Reasoner] Found {silent_count} contradictions "
            f"({explicit_count} explicit updates, {len(comparisons)} total pairs) "
            f"for entity {entity_id[:8]}..."
        )
        logger.info(
            "Reasoning complete for entity=%s: %d comparisons persisted "
            "(%d silent contradictions, %d explicit updates), %d duplicate pairs dropped.",
            entity_id,
            len(comparisons),
            silent_count,
            explicit_count,
            dropped_count,
        )

        return comparisons
