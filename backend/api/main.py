import os
import asyncio
import json
import uuid
import datetime
import logging
from typing import Dict, List, Any, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger("api")
logging.basicConfig(level=logging.INFO)

from backend.core.db import db
from backend.core.config import settings
from backend.core.models import EntityTypeEnum, ReviewActionEnum
from backend.engine.retrieval_agent import RetrievalAgent
from backend.engine.extractor_engine import ExtractorEngine
from backend.engine.drift_reasoning_engine import DriftReasoningEngine
from backend.eval.eval_harness import EvalHarness
from backend.eval.eval_cases_seed import seed_eval_cases
from backend.api.websocket_manager import ws_manager

app = FastAPI(title="autopsy.ai API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── In-memory pipeline status tracker ────────────────────────────────────────
_pipeline_status: Dict[str, Dict[str, Any]] = {}


# ─── Startup: seed DB entities only — NO pipeline execution on startup ─────────
@app.on_event("startup")
async def startup_event():
    """
    BUG #1 FIX: Only seed entities and eval cases on startup.
    Never trigger the investigation pipeline during startup — that deadlocked the server
    when external HTTP calls timed out, preventing ANY response to the frontend.
    Pipeline is triggered explicitly by the user via POST /investigate or GET /seed-demo.
    """
    seed_eval_cases()
    await _seed_default_entities_only()
    logger.info("autopsy.ai startup complete — entities seeded, pipeline ready for user triggers.")


async def _seed_default_entities_only():
    """Inserts the four canonical entities if they don't already exist. No pipeline calls."""
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) as cnt FROM entities")
    if cur.fetchone()["cnt"] == 0:
        default_entities = [
            ("PM-KISAN Scheme", "pm-kisan-scheme", "government_scheme"),
            ("Ayushman Bharat PM-JAY", "ayushman-bharat-pmjay", "government_scheme"),
            ("OpenAI API Terms of Service", "openai-api-tos", "corporate_policy"),
            ("Twitter / X API Access & Pricing", "twitter-x-api-policy", "corporate_policy"),
        ]
        for name, slug, etype in default_entities:
            cur.execute("""
            INSERT OR IGNORE INTO entities (id, name, canonical_slug, entity_type, is_featured, created_at, updated_at)
            VALUES (?, ?, ?, ?, 1, ?, ?)
            """, (
                str(uuid.uuid4()), name, slug, etype,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
                datetime.datetime.now(datetime.timezone.utc).isoformat()
            ))
        conn.commit()
        logger.info("Seeded 4 default featured entities.")
    else:
        # Ensure default canonical slugs are marked is_featured = 1
        featured_slugs = ["pm-kisan-scheme", "ayushman-bharat-pmjay", "openai-api-tos", "twitter-x-api-policy"]
        for s in featured_slugs:
            cur.execute("UPDATE entities SET is_featured = 1 WHERE canonical_slug = ?", (s,))
        conn.commit()
    conn.close()


# ─── Pydantic Request Models ───────────────────────────────────────────────────
class CreateEntityRequest(BaseModel):
    name: str
    entity_type: EntityTypeEnum = EntityTypeEnum.GOVERNMENT_SCHEME


class ReviewRequest(BaseModel):
    action: ReviewActionEnum
    notes: Optional[str] = None
    reviewer_id: Optional[str] = "auditor_1"


class RegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = "Forensics Investigator"


class LoginRequest(BaseModel):
    email: str
    password: str


def hash_password(password: str) -> str:
    import hashlib
    salt = "autopsy_salt_v2"
    return hashlib.sha256(f"{salt}{password}".encode("utf-8")).hexdigest()


# ─── Auth Endpoints ────────────────────────────────────────────────────────────
@app.post("/api/auth/register")
def register_user(req: RegisterRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters.")

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE lower(email) = lower(?)", (email,))
    if cur.fetchone():
        conn.close()
        raise HTTPException(status_code=400, detail="An account with this email already exists.")

    user_id = str(uuid.uuid4())
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute(
        "INSERT INTO users (id, email, display_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, email, req.full_name or "Investigator", "investigator", now)
    )
    conn.commit()
    conn.close()

    return {
        "status": "success",
        "user": {
            "id": user_id,
            "email": email,
            "name": req.full_name or "Investigator",
            "role": "investigator",
        },
        "token": f"token_{user_id}",
    }


@app.post("/api/auth/login")
def login_user(req: LoginRequest):
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="Please enter a valid email address.")
    if not req.password:
        raise HTTPException(status_code=400, detail="Password is required.")

    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, email, display_name, role FROM users WHERE lower(email) = lower(?)", (email,))
    user = cur.fetchone()

    if not user:
        user_id = str(uuid.uuid4())
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cur.execute(
            "INSERT INTO users (id, email, display_name, role, created_at) VALUES (?, ?, ?, ?, ?)",
            (user_id, email, email.split("@")[0].capitalize(), "investigator", now)
        )
        conn.commit()
        conn.close()
        user_data = {
            "id": user_id,
            "email": email,
            "name": email.split("@")[0].capitalize(),
            "role": "investigator",
        }
    else:
        conn.close()
        user_data = {
            "id": user["id"],
            "email": user["email"],
            "name": user["display_name"],
            "role": user["role"],
        }

    return {
        "status": "success",
        "user": user_data,
        "token": f"token_{user_data['id']}",
    }


class RecordHistoryRequest(BaseModel):
    entity_id: str
    entity_name: str
    contradiction_count: Optional[int] = 0
    comparison_count: Optional[int] = 0


@app.get("/api/users/{user_id}/history")
def get_user_history(user_id: str):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT h.id, h.user_id, h.entity_id, h.entity_name, h.contradiction_count, h.comparison_count, h.searched_at,
               e.canonical_slug, e.entity_type
        FROM user_search_history h
        LEFT JOIN entities e ON e.id = h.entity_id
        WHERE h.user_id = ?
        ORDER BY h.searched_at DESC
        LIMIT 50
    """, (user_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/users/{user_id}/history")
def record_user_history(user_id: str, req: RecordHistoryRequest):
    conn = db.get_connection()
    cur = conn.cursor()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cur.execute(
        "SELECT id FROM user_search_history WHERE user_id = ? AND (entity_id = ? OR lower(entity_name) = lower(?))",
        (user_id, req.entity_id, req.entity_name)
    )
    existing = cur.fetchone()
    if existing:
        cur.execute("""
            UPDATE user_search_history
            SET entity_id = ?, entity_name = ?, contradiction_count = ?, comparison_count = ?, searched_at = ?
            WHERE id = ?
        """, (req.entity_id, req.entity_name, req.contradiction_count or 0, req.comparison_count or 0, now, existing["id"]))
    else:
        history_id = str(uuid.uuid4())
        cur.execute("""
            INSERT INTO user_search_history (id, user_id, entity_id, entity_name, contradiction_count, comparison_count, searched_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (history_id, user_id, req.entity_id, req.entity_name, req.contradiction_count or 0, req.comparison_count or 0, now))
    conn.commit()
    conn.close()
    return {"status": "success"}


@app.delete("/api/users/{user_id}/history/{history_id}")
def delete_user_history(user_id: str, history_id: str):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM user_search_history WHERE id = ? AND user_id = ?", (history_id, user_id))
    conn.commit()
    conn.close()
    return {"status": "success"}
@app.get("/")
def root():
    return {
        "system": "autopsy.ai",
        "version": "2.0.0",
        "status": "ONLINE",
        "extractor_model": settings.EXTRACTOR_MODEL,
        "reasoner_model": settings.REASONER_MODEL,
    }


@app.get("/api/system/status")
def get_system_status():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) as cnt FROM entities")
    entity_count = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM comparisons")
    comparison_count = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM comparisons WHERE requires_human_review = 1")
    review_queue_count = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM eval_runs")
    eval_run_count = cur.fetchone()["cnt"]
    conn.close()

    missing_keys = []
    if not os.getenv("GEMINI_API_KEY") and not os.getenv("OPENROUTER_API_KEY"):
        missing_keys.append("GEMINI_API_KEY or OPENROUTER_API_KEY")
    if not os.getenv("TAVILY_API_KEY"):
        missing_keys.append("TAVILY_API_KEY")

    cost_summary = db.get_cost_summary()
    return {
        "status": "ONLINE",
        "entities": entity_count,
        "comparisons": comparison_count,
        "review_queue_count": review_queue_count,
        "eval_runs": eval_run_count,
        "grand_total_usd": cost_summary["grand_total_usd"],
        "grand_total_tokens": cost_summary["grand_total_tokens"],
        "extractor_model": settings.EXTRACTOR_MODEL,
        "reasoner_model": settings.REASONER_MODEL,
        "keys_configured": len(missing_keys) == 0,
        "missing_keys": missing_keys,
    }


@app.get("/api/system/costs")
def get_system_costs():
    return db.get_cost_summary()


@app.get("/api/system/audit-log")
def get_audit_log():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, actor_type, actor_id, action, target_table, target_id, payload, created_at
        FROM audit_log
        ORDER BY created_at DESC
        LIMIT 50
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "actor_type": r["actor_type"],
            "actor_id": r["actor_id"],
            "action": r["action"],
            "target_table": r["target_table"],
            "target_id": r["target_id"],
            "payload": json.loads(r["payload"]) if r["payload"] else {},
            "created_at": r["created_at"],
        }
        for r in rows
    ]


# ─── Entity Endpoints ──────────────────────────────────────────────────────────
@app.get("/api/entities")
def list_entities():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT e.id, e.name, e.canonical_slug, e.entity_type, e.is_featured, e.created_at, e.updated_at,
               (SELECT count(*) FROM documents d WHERE d.entity_id = e.id) as document_count,
               (SELECT count(*) FROM comparisons c WHERE c.entity_id = e.id) as comparison_count,
               (SELECT count(*) FROM comparisons c WHERE c.entity_id = e.id AND c.verdict = 'silent_contradiction') as contradiction_count,
               (SELECT count(*) FROM retrieval_failures rf WHERE rf.entity_id = e.id) as failure_count,
               (SELECT fetch_status FROM documents d WHERE d.entity_id = e.id ORDER BY fetched_at DESC LIMIT 1) as latest_fetch_status,
               (SELECT fetched_at FROM documents d WHERE d.entity_id = e.id ORDER BY fetched_at DESC LIMIT 1) as latest_fetched_at
        FROM entities e
        ORDER BY e.is_featured DESC, e.updated_at DESC
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/entities")
def create_entity(req: CreateEntityRequest):
    slug = req.name.lower().strip().replace(" ", "-").replace("/", "-")
    conn = db.get_connection()
    cur = conn.cursor()

    # Check if entity already exists by name or slug
    cur.execute("SELECT id, name, canonical_slug, entity_type FROM entities WHERE canonical_slug = ? OR lower(name) = lower(?)", (slug, req.name.strip()))
    existing = cur.fetchone()
    if existing:
        conn.close()
        return {"id": existing["id"], "name": existing["name"], "canonical_slug": existing["canonical_slug"], "entity_type": existing["entity_type"]}

    entity_id = str(uuid.uuid4())
    try:
        cur.execute("""
        INSERT INTO entities (id, name, canonical_slug, entity_type, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (
            entity_id, req.name.strip(), slug, req.entity_type.value,
            datetime.datetime.now(datetime.timezone.utc).isoformat(),
            datetime.datetime.now(datetime.timezone.utc).isoformat()
        ))
        conn.commit()
    except Exception:
        conn.close()
        raise HTTPException(status_code=400, detail="Entity with similar name already exists.")
    conn.close()
    return {"id": entity_id, "name": req.name, "canonical_slug": slug, "entity_type": req.entity_type.value}


# ─── Investigation Trigger ───────────────────────────────────────────────────
@app.post("/api/entities/{entity_id}/investigate")
async def trigger_investigation(entity_id: str):
    """
    Executes the full 4-stage live investigation pipeline (retrieval -> extraction -> drift reasoning),
    broadcasting live progress via WebSocket /ws/live and returning fresh comparisons.
    """
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM entities WHERE id = ?", (entity_id,))
    entity = cur.fetchone()
    conn.close()

    if not entity:
        raise HTTPException(status_code=404, detail="Entity not found")

    # A new investigation must never reuse claims or comparisons from an older run.
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM comparisons WHERE entity_id = ?", (entity_id,))
    cur.execute(
        "DELETE FROM claims WHERE document_id IN "
        "(SELECT id FROM documents WHERE entity_id = ?)",
        (entity_id,),
    )
    conn.commit()
    conn.close()

    # Mark pipeline as running
    _pipeline_status[entity_id] = {
        "status": "RUNNING",
        "stage": "retrieval",
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "documents_count": 0,
        "comparisons_count": 0,
    }

    # Run the full live pipeline — raises HTTPException on any failure
    await run_full_investigation_pipeline(entity_id, entity["name"])

    # Return fresh comparisons directly
    fresh_comparisons = get_entity_comparisons(entity_id)

    # Attach document count
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) as cnt FROM documents WHERE entity_id = ?", (entity_id,))
    doc_count = cur.fetchone()["cnt"]
    conn.close()

    return {
        "status": "INVESTIGATION_COMPLETE",
        "entity_id": entity_id,
        "entity_name": entity["name"],
        "documents_analyzed": doc_count,
        "comparisons": fresh_comparisons,
    }


@app.get("/api/entities/{entity_id}/pipeline-status")
def get_pipeline_status(entity_id: str):
    """Polling endpoint for frontend to check pipeline progress without WebSocket."""
    status = _pipeline_status.get(entity_id, {"status": "IDLE"})
    # Attach current comparison & document count from DB
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("SELECT count(*) as cnt FROM comparisons WHERE entity_id = ?", (entity_id,))
    count = cur.fetchone()["cnt"]
    cur.execute("SELECT count(*) as cnt FROM documents WHERE entity_id = ?", (entity_id,))
    doc_count = cur.fetchone()["cnt"]
    conn.close()
    return {**status, "comparisons_count": count, "document_count": doc_count}


# ─── Seed-demo endpoint removed ───────────────────────────────────────────────
# The /api/seed-demo endpoint that bypassed the live pipeline with static mock data
# has been permanently removed. All audit data is generated by the live pipeline
# via POST /api/entities/{id}/investigate.


# ─── Full 4-Stage Investigation Pipeline ──────────────────────────────────────
async def run_full_investigation_pipeline(entity_id: str, entity_name: str):
    """
    Executes the live pipeline: Retrieval → Extraction → Drift Reasoning.
    Any failure in any stage raises HTTPException(500) with the exact error message
    so the frontend and developer can diagnose API key / network issues immediately.
    NO silent swallowing of errors. NO static fallbacks.
    """
    missing_keys = []
    if not settings.TAVILY_API_KEY:
        missing_keys.append("TAVILY_API_KEY")
    if not settings.GEMINI_API_KEY and not settings.OPENROUTER_API_KEY:
        missing_keys.append("GEMINI_API_KEY or OPENROUTER_API_KEY")

    if missing_keys:
        error_msg = f"Missing required live pipeline API keys: {', '.join(missing_keys)}"
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "configuration", "error": error_msg}
        raise HTTPException(status_code=500, detail=error_msg)

    print(f"\n[Pipeline] Starting investigation for: '{entity_name}'...")
    _pipeline_status[entity_id] = {
        "status": "RUNNING",
        "stage": "retrieval",
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    await ws_manager.broadcast(
        event_type="pipeline_start",
        agent="Pipeline Orchestrator",
        message=f"Starting investigation pipeline for: {entity_name}...",
        data={"entity_id": entity_id, "stage": "retrieval"},
    )
    await asyncio.sleep(0.2)

    # ── Stage 1: Live Retrieval (Tavily → Wikipedia → PIB) ─────────────────
    try:
        retrieval_agent = RetrievalAgent()
        docs = await retrieval_agent.retrieve_for_entity(entity_id, entity_name)
    except RuntimeError as exc:
        error_msg = f"[RETRIEVAL FAILED] {exc}"
        logger.error("Pipeline retrieval error for entity=%s: %s", entity_id, error_msg)
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "retrieval", "error": error_msg}
        await ws_manager.broadcast(
            event_type="pipeline_error",
            agent="Retrieval Agent",
            message=error_msg,
            data={"entity_id": entity_id, "stage": "retrieval", "error": error_msg},
        )
        if str(exc) == "Retrieval timed out. Please retry.":
            raise HTTPException(status_code=500, detail=str(exc)) from exc
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as exc:
        error_msg = f"[RETRIEVAL UNEXPECTED ERROR] {type(exc).__name__}: {exc}"
        logger.exception("Unexpected retrieval error for entity=%s", entity_id)
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "retrieval", "error": error_msg}
        await ws_manager.broadcast(
            event_type="pipeline_error",
            agent="Retrieval Agent",
            message=error_msg,
            data={"entity_id": entity_id, "stage": "retrieval", "error": error_msg},
        )
        raise HTTPException(status_code=500, detail=error_msg)

    if not docs:
        error_msg = "Retrieval timed out. Please retry."
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "retrieval", "error": error_msg}
        raise HTTPException(status_code=500, detail=error_msg)

    status_label = docs[0].fetch_status if docs else "empty"
    _pipeline_status[entity_id]["stage"] = "extraction"
    _pipeline_status[entity_id]["documents_count"] = len(docs)
    await ws_manager.broadcast(
        event_type="retrieval_complete",
        agent="Retrieval Agent",
        message=f"Retrieved {len(docs)} live documents via {status_label}.",
        data={"documents_count": len(docs), "fetch_status": status_label, "stage": "extraction"},
    )
    await asyncio.sleep(0.1)

    # ── Stage 2: Extraction (Gemini / Model 1) ────────────────────────────
    try:
        extractor = ExtractorEngine()
        claims = await extractor.extract_documents(
            [
                (doc.id, doc.extracted_text, doc.published_at_guess)
                for doc in docs
            ],
            entity_name,
        )
        total_claims = len(claims)
    except Exception as exc:
        error_msg = f"[EXTRACTION FAILED] {type(exc).__name__}: {exc}"
        logger.exception("Extraction error for entity=%s", entity_id)
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "extraction", "error": error_msg}
        await ws_manager.broadcast(
            event_type="pipeline_error",
            agent="Extractor Engine",
            message=error_msg,
            data={"entity_id": entity_id, "stage": "extraction", "error": error_msg},
        )
        raise HTTPException(status_code=500, detail=error_msg)

    if total_claims == 0:
        error_msg = (
            f"[EXTRACTION] 0 claims extracted from {len(docs)} documents for '{entity_name}'. "
            "Check GEMINI_API_KEY and that the documents contain parseable policy text."
        )
        logger.error(error_msg)
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "extraction", "error": error_msg}
        await ws_manager.broadcast(
            event_type="pipeline_error",
            agent="Extractor Engine",
            message=error_msg,
            data={"entity_id": entity_id, "stage": "extraction", "error": error_msg},
        )
        raise HTTPException(status_code=500, detail=error_msg)

    print(f"[Extractor] Extracted {total_claims} claims from {len(docs)} documents.")
    _pipeline_status[entity_id]["stage"] = "reasoning"
    _pipeline_status[entity_id]["claims_count"] = total_claims
    await ws_manager.broadcast(
        event_type="extraction_complete",
        agent="Extractor Engine (Model 1 — Gemini)",
        message=f"Extracted {total_claims} grounded claims from {len(docs)} live documents.",
        data={"claims_count": total_claims, "stage": "reasoning"},
    )
    await asyncio.sleep(0.1)

    # ── Stage 3: Drift Reasoning (OpenRouter / Model 2) ───────────────────
    try:
        reasoning_engine = DriftReasoningEngine()
        comparisons = await reasoning_engine.run_pipeline_for_entity(entity_id)
    except RuntimeError as exc:
        error_msg = f"[REASONING FAILED] {exc}"
        logger.error("Reasoning error for entity=%s: %s", entity_id, error_msg)
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "reasoning", "error": error_msg}
        await ws_manager.broadcast(
            event_type="pipeline_error",
            agent="Drift Reasoning Engine",
            message=error_msg,
            data={"entity_id": entity_id, "stage": "reasoning", "error": error_msg},
        )
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as exc:
        error_msg = f"[REASONING UNEXPECTED ERROR] {type(exc).__name__}: {exc}"
        logger.exception("Unexpected reasoning error for entity=%s", entity_id)
        _pipeline_status[entity_id] = {"status": "ERROR", "stage": "reasoning", "error": error_msg}
        await ws_manager.broadcast(
            event_type="pipeline_error",
            agent="Drift Reasoning Engine",
            message=error_msg,
            data={"entity_id": entity_id, "stage": "reasoning", "error": error_msg},
        )
        raise HTTPException(status_code=500, detail=error_msg)

    silent_count = sum(1 for c in comparisons if c.verdict == "silent_contradiction")
    explicit_count = sum(1 for c in comparisons if c.verdict == "explicit_update")
    review_count = sum(1 for c in comparisons if c.requires_human_review)

    print(
        f"[Reasoner] Found {silent_count} contradictions "
        f"({explicit_count} explicit updates, {len(comparisons)} total).\n"
    )

    # Update entity timestamp
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute(
        "UPDATE entities SET updated_at = ? WHERE id = ?",
        (datetime.datetime.now(datetime.timezone.utc).isoformat(), entity_id),
    )
    conn.commit()
    conn.close()

    _pipeline_status[entity_id] = {
        "status": "COMPLETE",
        "stage": "done",
        "documents_count": len(docs),
        "claims_count": total_claims,
        "comparisons_count": len(comparisons),
        "silent_contradictions": silent_count,
    }

    await ws_manager.broadcast(
        event_type="reasoning_complete",
        agent="Drift Reasoning Engine (Model 2 — OpenRouter)",
        message=(
            f"Completed {len(comparisons)} pairwise comparisons "
            f"({silent_count} silent contradictions, {review_count} flagged for human review)."
        ),
        data={
            "comparisons_count": len(comparisons),
            "silent_contradictions": silent_count,
            "review_queue": review_count,
            "entity_id": entity_id,
            "stage": "done",
        },
    )
    logger.info(
        "Pipeline complete for entity=%s: %d comparisons (%d silent contradictions).",
        entity_id,
        len(comparisons),
        silent_count,
    )


# ─── Comparisons & Workspace Detail ───────────────────────────────────────────
@app.get("/api/entities/{entity_id}/comparisons")
def get_entity_comparisons(entity_id: str):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.entity_id, c.claim_a_id, c.claim_b_id, c.verdict, c.confidence, c.reasoning,
               c.requires_human_review, c.reasoner_model_version, c.created_at,
               ca.raw_excerpt as claim_a_excerpt, ca.claim_type as claim_a_type,
               da.published_at as claim_a_date, da.source_url as claim_a_url,
               cb.raw_excerpt as claim_b_excerpt, cb.claim_type as claim_b_type,
               db.published_at as claim_b_date, db.source_url as claim_b_url,
               (SELECT action FROM review_actions ra WHERE ra.comparison_id = c.id ORDER BY created_at DESC LIMIT 1) as latest_review_action
        FROM comparisons c
        JOIN claims ca ON c.claim_a_id = ca.id
        JOIN documents da ON ca.document_id = da.id
        JOIN claims cb ON c.claim_b_id = cb.id
        JOIN documents db ON cb.document_id = db.id
        WHERE c.entity_id = ?
        ORDER BY c.created_at DESC
    """, (entity_id,))
    rows = cur.fetchall()
    conn.close()

    formatted = []
    for r in rows:
        formatted.append({
            "comparisonId": r["id"],
            "entityId": r["entity_id"],
            "verdict": r["verdict"],
            "confidence": float(r["confidence"]),
            "reasoning": r["reasoning"],
            "requiresHumanReview": bool(r["requires_human_review"]),
            "latestReviewAction": r["latest_review_action"],
            "claimA": {
                "excerpt": r["claim_a_excerpt"],
                "claimType": r["claim_a_type"],
                "publishedAt": r["claim_a_date"],
                "sourceUrl": r["claim_a_url"],
            },
            "claimB": {
                "excerpt": r["claim_b_excerpt"],
                "claimType": r["claim_b_type"],
                "publishedAt": r["claim_b_date"],
                "sourceUrl": r["claim_b_url"],
            },
        })
    return formatted


# ─── Sources & Failure Logs ────────────────────────────────────────────────────
@app.get("/api/entities/{entity_id}/failures")
def get_entity_failures(entity_id: str):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, source_url, reason_code, occurred_at, fallback_used
        FROM retrieval_failures
        WHERE entity_id = ?
        ORDER BY occurred_at DESC
    """, (entity_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/entities/{entity_id}/sources")
def get_entity_sources(entity_id: str):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT s.id, s.source_url, s.source_type, s.first_seen_at, s.last_checked_at,
               (SELECT count(*) FROM documents d WHERE d.source_id = s.id) as snapshot_count
        FROM sources s
        WHERE s.entity_id = ?
        ORDER BY s.first_seen_at DESC
    """, (entity_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ─── Review Actions (HITL) ─────────────────────────────────────────────────────
@app.get("/api/comparisons/review-queue")
def get_review_queue():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT c.id, c.entity_id, c.verdict, c.confidence, c.reasoning, e.name as entity_name,
               ca.raw_excerpt as claim_a_excerpt, da.published_at as claim_a_date, da.source_url as claim_a_url,
               cb.raw_excerpt as claim_b_excerpt, db.published_at as claim_b_date, db.source_url as claim_b_url
        FROM comparisons c
        JOIN entities e ON c.entity_id = e.id
        JOIN claims ca ON c.claim_a_id = ca.id
        JOIN documents da ON ca.document_id = da.id
        JOIN claims cb ON c.claim_b_id = cb.id
        JOIN documents db ON cb.document_id = db.id
        WHERE c.requires_human_review = 1
        ORDER BY c.confidence ASC
    """)
    rows = cur.fetchall()
    conn.close()
    return [
        {
            "comparisonId": r["id"],
            "entityId": r["entity_id"],
            "entityName": r["entity_name"],
            "verdict": r["verdict"],
            "confidence": float(r["confidence"]),
            "reasoning": r["reasoning"],
            "claimA": {"excerpt": r["claim_a_excerpt"], "publishedAt": r["claim_a_date"], "sourceUrl": r["claim_a_url"]},
            "claimB": {"excerpt": r["claim_b_excerpt"], "publishedAt": r["claim_b_date"], "sourceUrl": r["claim_b_url"]},
        }
        for r in rows
    ]


@app.post("/api/comparisons/{comparison_id}/review")
def record_review(comparison_id: str, req: ReviewRequest):
    conn = db.get_connection()
    cur = conn.cursor()
    review_id = str(uuid.uuid4())
    cur.execute("""
    INSERT INTO review_actions (id, comparison_id, reviewer_id, action, notes, created_at)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (review_id, comparison_id, req.reviewer_id, req.action.value, req.notes, datetime.datetime.now(datetime.timezone.utc).isoformat()))
    cur.execute("UPDATE comparisons SET requires_human_review = 0 WHERE id = ?", (comparison_id,))
    conn.commit()
    conn.close()

    db.log_audit("user", req.reviewer_id, "review_recorded", "review_actions", review_id, {"comparison_id": comparison_id, "action": req.action.value})
    return {"status": "SUCCESS", "comparison_id": comparison_id, "action": req.action.value}


# ─── Eval System Endpoints ─────────────────────────────────────────────────────
@app.get("/api/eval/runs")
def list_eval_runs():
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, run_at, extractor_model_version, reasoner_model_version, prompt_version_hash,
               total_cases, accuracy, false_positive_rate, false_negative_rate, promoted_to_production
        FROM eval_runs
        ORDER BY run_at DESC
        LIMIT 20
    """)
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.get("/api/eval/runs/{run_id}/results")
def get_eval_run_results(run_id: str):
    conn = db.get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT ecr.id, ecr.eval_run_id, ecr.eval_case_id, ecr.model_label, ecr.model_confidence, ecr.correct,
               ec.claim_a_excerpt, ec.claim_b_excerpt, ec.claim_type, ec.human_label, ec.notes
        FROM eval_case_results ecr
        JOIN eval_cases ec ON ecr.eval_case_id = ec.id
        WHERE ecr.eval_run_id = ?
    """, (run_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/eval/run")
async def trigger_eval_run():
    harness = EvalHarness()
    result = await harness.run()
    promoted = await harness.persist_and_gate(result)
    return {
        "status": "EVAL_COMPLETE",
        "total_cases": result.total_cases,
        "accuracy": result.accuracy,
        "false_positive_rate": result.false_positive_rate,
        "false_negative_rate": result.false_negative_rate,
        "promoted_to_production": promoted,
        "per_case_results": result.per_case_results,
    }


# ─── WebSocket Endpoint ────────────────────────────────────────────────────────
@app.websocket("/ws/live")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({
            "event_type": "connected",
            "stage": "idle",
            "agent": "System Gateway",
            "message": "Connected to autopsy.ai live pipeline telemetry.",
            "data": {"status": "ONLINE", "stage": "idle"},
        })
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception:
        ws_manager.disconnect(websocket)
