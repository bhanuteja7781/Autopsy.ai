from __future__ import annotations
import difflib
import json
import logging
import uuid
import datetime
import re
import asyncio
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ValidationError, field_validator
from backend.core.config import settings
from backend.core.db import db
from backend.core.llm_client import llm_client

logger = logging.getLogger("extractor_engine")

EXTRACTOR_MODEL_VERSION = settings.EXTRACTOR_MODEL
FUZZY_MATCH_THRESHOLD = 0.92


def sanitize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(
        r"(?i)\[(?:home|menu|navigation|search|jump to content|skip to content|"
        r"log in|sign in|register|subscribe|next page|previous page)\]\([^)]*\)",
        " ",
        text,
    )
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\([^)]*#[\w-]+[^)]*\)", "", text)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"(?im)^\s*(?:[+*#-]\s*)?(?:home|menu|navigation|search|"
                  r"jump to content|skip to content|log in|sign in|register|"
                  r"subscribe|next page|previous page|read more)\s*$", "", text)
    text = re.sub(r"\[/?(?:static/images/|images/)[^\]]*\]", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).strip()

class RawClaim(BaseModel):
    claim_type: str
    normalized_value: dict = Field(default_factory=dict)
    raw_excerpt: str = Field(min_length=3)
    extraction_confidence: float = Field(ge=0.0, le=1.0)
    effective_date: Optional[str] = None

    @field_validator("claim_type")
    @classmethod
    def validate_claim_type(cls, v: str) -> str:
        allowed = {"eligibility", "amount", "deadline", "coverage", "prohibition", "exemption", "requirement", "benefit", "other"}
        if str(v).lower() not in allowed:
            return "other"
        return str(v).lower()

class GroundedClaim(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    document_id: str
    claim_type: str
    normalized_value: dict
    raw_excerpt: str
    excerpt_char_start: int
    excerpt_char_end: int
    extraction_confidence: float
    extractor_model_version: str = EXTRACTOR_MODEL_VERSION
    created_at: str = Field(default_factory=lambda: datetime.datetime.utcnow().isoformat())
    effective_date: Optional[str] = None

EXTRACTION_SYSTEM_PROMPT = """You extract substantive policy and scheme claims from legal and government documents.
DOMAIN CONSTRAINT: Determine the primary subject of the requested entity. Extract ONLY substantive claims about that exact subject.

STRICT SUBSTANTIVE EXTRACTION RULES:
1. IGNORE pure administrative and procedural metadata such as bill passage dates, presidential assent dates, signature dates, gazette issue numbers, or printing press locations.
2. Extract ONLY operative legal clauses, behavioral rules, rights, obligations, caps, or eligibility terms that directly affect citizens or beneficiaries.
3. Return ONLY a JSON array of claims. Each claim MUST include:
   - claim_type: one of [eligibility, amount, deadline, coverage, other]
   - normalized_value: a structured object capturing the rule (e.g. {"unit": "hectares", "operator": "<=", "value": 2})
   - raw_excerpt: the EXACT verbatim sentence or clause from the source text that supports this substantive claim.
   - extraction_confidence: confidence (0.0-1.0) that this is a genuine operative rule.
   - effective_date: official document publication or notification date (e.g. 2019-12-11, 2024-03-11).

CRITICAL CHRONOLOGY RULE:
- `effective_date` MUST be the official publication date, press release date, or gazette notification date of the document itself (e.g., 2019, 2020, 2024).
- DO NOT use historical qualification dates or cut-off dates mentioned INSIDE the text body (e.g. "entered India on or before 31st December 2014") as the document's effective_date.
- If no explicit publication date is found, infer it from the source publication metadata or set `effective_date` to null."""

class ExtractorEngine:
    def __init__(self):
        pass

    async def extract_and_persist(
        self, document_id: str, document_text: str, published_date: Optional[str] = None,
        entity_name: Optional[str] = None,
    ) -> list[GroundedClaim]:
        grounded_claims = await self.extract(
            document_id, sanitize_text(document_text), published_date, entity_name
        )

        self._persist_claims(grounded_claims)

        # Trace extraction tokens and cost
        tok_in = max(20, len(document_text) // 4)
        tok_out = max(10, len(grounded_claims) * 45)
        db.log_cost(None, "extraction", tokens_in=tok_in, tokens_out=tok_out, cost_usd=round((tok_in + tok_out) * 0.000003, 4))
        db.log_audit("system", None, "extraction_completed", "claims", document_id, {"grounded_claims_count": len(grounded_claims)})

        print(f"[Extractor] Extracted {len(grounded_claims)} claims for document {document_id[:8]}...")
        logger.info("[Extractor] Extracted %d grounded claims for doc=%s", len(grounded_claims), document_id)

        return grounded_claims

    def _persist_claims(self, grounded_claims: list[GroundedClaim]) -> None:
        if not grounded_claims:
            return

        conn = db.get_connection()
        cur = conn.cursor()
        for gc in grounded_claims:
            cur.execute("""
            INSERT OR REPLACE INTO claims
            (id, document_id, claim_type, normalized_value, raw_excerpt, excerpt_char_start, excerpt_char_end, extraction_confidence, extractor_model_version, created_at, effective_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                gc.id, gc.document_id, gc.claim_type, json.dumps(gc.normalized_value),
                gc.raw_excerpt, gc.excerpt_char_start, gc.excerpt_char_end,
                gc.extraction_confidence, gc.extractor_model_version, gc.created_at,
                gc.effective_date
            ))
        conn.commit()
        conn.close()

    async def extract_documents(
        self, documents: list[tuple[str, str, Optional[str]]], entity_name: str
    ) -> list[GroundedClaim]:
        """Extract documents with high concurrency (8 parallel workers), persisting claims serially for SQLite safety."""
        semaphore = asyncio.Semaphore(8)

        async def _safe_extract(doc_id: str, text: str, pub_date: Optional[str]) -> list[GroundedClaim]:
            async with semaphore:
                try:
                    return await self.extract(doc_id, text, pub_date, entity_name)
                except RuntimeError:
                    raise  # propagate hard LLM failures to the pipeline
                except Exception as exc:
                    logger.warning("Failed extracting claims for doc=%s: %s", doc_id, exc)
                    return []

        results = await asyncio.gather(*(
            _safe_extract(document_id, text, published_date)
            for document_id, text, published_date in documents
        ))
        claims = [claim for result in results for claim in result]
        for result in results:
            if result:
                self._persist_claims(result)
        return claims

    async def extract(
        self, document_id: str, document_text: str, published_date: Optional[str] = None,
        entity_name: Optional[str] = None,
    ) -> list[GroundedClaim]:
        document_text = sanitize_text(document_text)
        if not document_text or len(document_text) < 30:
            return []

        raw_claims = await self._call_llm_with_schema_retry(document_text, published_date, entity_name)

        grounded: list[GroundedClaim] = []
        discarded_count = 0

        for raw in raw_claims:
            raw.raw_excerpt = sanitize_text(raw.raw_excerpt)
            if not raw.raw_excerpt or raw.raw_excerpt.startswith("["):
                discarded_count += 1
                continue
            location = self._locate_excerpt(raw.raw_excerpt, document_text)
            if location is None:
                discarded_count += 1
                logger.info(
                    "Discarding ungrounded claim for document=%s: excerpt not found (claim_type=%s, excerpt_preview=%.60r)",
                    document_id, raw.claim_type, raw.raw_excerpt,
                )
                continue

            start, end, match_ratio = location
            adjusted_confidence = raw.extraction_confidence * match_ratio  # penalize fuzzy matches

            normalized_value = dict(raw.normalized_value) if isinstance(raw.normalized_value, dict) else {}
            if any(
                keyword in raw.raw_excerpt.lower()
                for keyword in ("arrived before", "cutoff date", "eligibility from", "proviso")
            ):
                normalized_value.pop("effective_date", None)
                normalized_value.pop("published_date", None)

            doc_effective_date = published_date or raw.effective_date
            if published_date:
                doc_effective_date = published_date

            grounded.append(
                GroundedClaim(
                    document_id=document_id,
                    claim_type=raw.claim_type,
                    normalized_value=normalized_value,
                    raw_excerpt=raw.raw_excerpt,
                    excerpt_char_start=start,
                    excerpt_char_end=end,
                    extraction_confidence=round(adjusted_confidence, 3),
                    effective_date=doc_effective_date,
                )
            )

        logger.info(
            "Extraction summary for doc=%s: %d raw claims extracted, %d grounded (retained), %d discarded by guardrail.",
            document_id, len(raw_claims), len(grounded), discarded_count,
        )

        # SAFETY NET: If LLM returned 0 grounded claims but the document has substantive text,
        # force-insert the first 3 meaningful sentences as generic 'other' claims.
        # This guarantees pairwise comparison always has material to work with.
        if len(grounded) == 0 and len(document_text.strip()) > 40:
            sentences = [s.strip() for s in document_text.split('.') if len(s.strip()) > 30]
            for sent in sentences[:3]:
                grounded.append(
                    GroundedClaim(
                        document_id=document_id,
                        claim_type="other",
                        normalized_value={"rule": "policy_statement"},
                        raw_excerpt=sent,
                        excerpt_char_start=document_text.find(sent),
                        excerpt_char_end=document_text.find(sent) + len(sent),
                        extraction_confidence=0.65,
                        effective_date=published_date,
                    )
                )
            if grounded:
                logger.info(
                    "Safety-net: inserted %d sentence-level claims for doc=%s (LLM returned 0 grounded).",
                    len(grounded), document_id,
                )

        return grounded

    async def _call_llm_with_schema_retry(
        self, document_text: str, published_date: Optional[str] = None,
        entity_name: Optional[str] = None, attempt: int = 0
    ) -> list[RawClaim]:
        try:
            clean_text = document_text[:3500]
            target_entity = entity_name or 'the requested entity'
            prompt = f"""Extract substantive policy rules, eligibility criteria, exemptions, prohibitions, and legal definitions regarding '{target_entity}' from the text.

STRICT FILTERING & DOMAIN RULES:
1. IGNORE pure administrative metadata such as bill passage dates, presidential assent dates, signature dates, gazette issue numbers, or printing press locations.
2. Extract ONLY operative legal clauses, behavioral rules, rights, caps, or eligibility terms that affect citizens or users.
3. DISCARD and IGNORE any content related to US universities, sports associations, foreign municipal codes, or unrelated regional art/college bodies.

CRITICAL CHRONOLOGY RULE:
- `effective_date` MUST be the official publication date, press release date, or gazette notification date of the document itself (e.g., 2019, 2020, 2024).
- DO NOT use historical qualification dates or cut-off dates mentioned INSIDE the text body (e.g. "entered India on or before 31st December 2014") as the document's effective_date.
- If no explicit publication date is found, infer it from the document URL/metadata or set `effective_date` to null.

Output ONLY a raw JSON array of grounded claims:
[{{"claim_type": "eligibility", "effective_date": "YYYY-MM-DD", "normalized_value": {{}}, "raw_excerpt": "EXACT verbatim sentence from text", "extraction_confidence": 0.95}}]

Source Publication Date Metadata: {published_date or 'not provided'}

Text:
{clean_text}
"""
            response_text = await asyncio.to_thread(
                llm_client.get_extraction_model().generate,
                prompt=prompt,
                system_instruction=(
                    f"{EXTRACTION_SYSTEM_PROMPT}\n"
                    f"DOMAIN CONSTRAINT: Determine the primary subject of '{target_entity}'. "
                    "Extract ONLY substantive claims regarding that exact subject. Ignore procedural passage dates and foreign/unrelated bodies."
                ),
            )
            from backend.core.llm_client import extract_json_array_str
            clean_json = extract_json_array_str(response_text) or response_text
            payload = json.loads(clean_json)
            if not isinstance(payload, list):
                if isinstance(payload, dict):
                    payload = [payload]
                else:
                    return []

            claims = []
            for item in payload:
                if isinstance(item, dict):
                    try:
                        claims.append(RawClaim(**item))
                    except ValidationError:
                        continue
            return claims
        except (json.JSONDecodeError, ValidationError) as e:
            # JSON parse failure → retry once, then return empty (not a hard failure)
            if attempt >= 1:
                logger.warning("Extraction schema retry exhausted for doc: %s", e)
                return []
            return await self._call_llm_with_schema_retry(
                document_text, published_date, entity_name, attempt=attempt + 1
            )
        except RuntimeError as exc:
            # LLM provider failure (OpenRouter down, all models failed, network RST)
            # Do NOT swallow — re-raise so the pipeline surfaces HTTP 500
            logger.error("Extraction LLM hard failure: %s", exc)
            raise
        except Exception as exc:
            # Unexpected error → retry once, then re-raise
            if attempt >= 1:
                logger.error("Extraction unexpected failure (attempt %d): %s", attempt, exc)
                raise RuntimeError(f"Extraction failed after retry: {exc}") from exc
            logger.warning("Extraction attempt %d failed (%s), retrying...", attempt, exc)
            return await self._call_llm_with_schema_retry(
                document_text, published_date, entity_name, attempt=attempt + 1
            )

    def _locate_excerpt(self, excerpt: str, document_text: str) -> Optional[tuple[int, int, float]]:
        import re

        # 1. Exact match
        idx = document_text.find(excerpt)
        if idx != -1:
            return idx, idx + len(excerpt), 1.0

        # 2. Case-insensitive match
        low_doc = document_text.lower()
        low_exc = excerpt.lower()
        idx = low_doc.find(low_exc)
        if idx != -1:
            return idx, idx + len(excerpt), 0.98

        # 3. Normalized whitespace match
        clean_doc = re.sub(r'\s+', ' ', document_text).strip()
        clean_exc = re.sub(r'\s+', ' ', excerpt).strip()
        idx = clean_doc.lower().find(clean_exc.lower())
        if idx != -1:
            return idx, min(len(document_text), idx + len(excerpt)), 0.95

        # 4. Fuzzy sliding window
        window = len(excerpt)
        best_ratio = 0.0
        best_span: Optional[tuple[int, int]] = None
        step = max(1, window // 8)

        for i in range(0, max(1, len(document_text) - window + 1), step):
            candidate = document_text[i:i + window]
            ratio = difflib.SequenceMatcher(None, clean_exc.lower(), candidate.lower()).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_span = (i, i + window)

        if best_span and best_ratio >= 0.80:
            return best_span[0], best_span[1], best_ratio

        # 5. Sentence-level matching handles excerpts normalized by the model.
        for sent in document_text.split('.'):
            sent_clean = sent.strip()
            if len(sent_clean) > 10:
                # Fast starts-with check before expensive SequenceMatcher
                if sent_clean.lower().startswith(clean_exc.lower()[:20]):
                    s_idx = document_text.find(sent_clean)
                    if s_idx != -1:
                        return s_idx, s_idx + len(sent_clean), 0.95
                ratio = difflib.SequenceMatcher(None, clean_exc.lower(), sent_clean.lower()).ratio()
                if ratio >= 0.72:
                    s_idx = document_text.find(sent_clean)
                    if s_idx != -1:
                        return s_idx, s_idx + len(sent_clean), ratio

        return None
