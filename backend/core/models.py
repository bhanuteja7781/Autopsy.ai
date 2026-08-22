from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from datetime import datetime

class EntityTypeEnum(str, Enum):
    GOVERNMENT_SCHEME = "government_scheme"
    CORPORATE_POLICY = "corporate_policy"
    SOFTWARE_CHANGELOG = "software_changelog"
    OTHER = "other"

class SourceTypeEnum(str, Enum):
    OFFICIAL_RELEASE = "official_release"
    NEWS_COVERAGE = "news_coverage"
    ARCHIVE_SNAPSHOT = "archive_snapshot"
    OTHER = "other"

class FetchStatusEnum(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"

class ClaimTypeEnum(str, Enum):
    ELIGIBILITY = "eligibility"
    AMOUNT = "amount"
    DEADLINE = "deadline"
    COVERAGE = "coverage"
    OTHER = "other"

class VerdictEnum(str, Enum):
    CONSISTENT = "consistent"
    EXPLICIT_UPDATE = "explicit_update"
    SILENT_CONTRADICTION = "silent_contradiction"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"

class ReviewActionEnum(str, Enum):
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"
    ESCALATED = "escalated"

class PipelineStageEnum(str, Enum):
    RETRIEVAL = "retrieval"
    EXTRACTION = "extraction"
    REASONING = "reasoning"

# Pydantic schema models
class EntityModel(BaseModel):
    id: str
    name: str
    canonical_slug: str
    entity_type: EntityTypeEnum
    created_at: str
    updated_at: str

class SourceModel(BaseModel):
    id: str
    entity_id: str
    source_url: str
    source_type: SourceTypeEnum
    first_seen_at: str
    last_checked_at: Optional[str] = None

class DocumentModel(BaseModel):
    id: str
    entity_id: str
    source_id: str
    source_url: str
    raw_snapshot_ref: str
    content_hash: str
    extracted_text: str
    language: str = "en"
    published_at: Optional[str] = None
    fetched_at: str
    fetch_status: FetchStatusEnum

class ClaimModel(BaseModel):
    id: str
    document_id: str
    claim_type: ClaimTypeEnum
    normalized_value: Dict[str, Any]
    raw_excerpt: str
    excerpt_char_start: int
    excerpt_char_end: int
    extraction_confidence: float
    extractor_model_version: str
    created_at: str

class ComparisonModel(BaseModel):
    id: str
    entity_id: str
    claim_a_id: str
    claim_b_id: str
    verdict: VerdictEnum
    confidence: float
    reasoning: str
    requires_human_review: bool
    reasoner_model_version: str
    created_at: str
    claim_a: Optional[Dict[str, Any]] = None
    claim_b: Optional[Dict[str, Any]] = None

class ReviewActionModel(BaseModel):
    id: str
    comparison_id: str
    reviewer_id: str
    action: ReviewActionEnum
    notes: Optional[str] = None
    created_at: str

class EvalCaseModel(BaseModel):
    id: str
    claim_a_excerpt: str
    claim_b_excerpt: str
    claim_type: ClaimTypeEnum
    human_label: VerdictEnum
    notes: Optional[str] = None

class EvalRunModel(BaseModel):
    id: str
    run_at: str
    extractor_model_version: str
    reasoner_model_version: str
    prompt_version_hash: str
    total_cases: int
    accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    promoted_to_production: bool

class CostLedgerModel(BaseModel):
    id: str
    entity_id: Optional[str]
    stage: PipelineStageEnum
    tokens_in: int
    tokens_out: int
    cost_usd: float
    created_at: str
