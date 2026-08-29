import os
import sqlite3
import json
import uuid
import datetime
from typing import Dict, List, Any, Optional

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "autopsy_dpr.db")

class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA busy_timeout=30000;")
        except Exception:
            pass
        return conn

    def _init_db(self):
        conn = self.get_connection()
        cur = conn.cursor()
        
        # 1. Users
        cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            display_name TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'researcher',
            created_at TEXT NOT NULL
        )
        """)

        # 2. Entities
        cur.execute("""
        CREATE TABLE IF NOT EXISTS entities (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            canonical_slug TEXT UNIQUE NOT NULL,
            entity_type TEXT NOT NULL,
            is_featured INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """)
        # Run migration if is_featured column missing
        try:
            cur.execute("ALTER TABLE entities ADD COLUMN is_featured INTEGER NOT NULL DEFAULT 0")
        except Exception:
            pass

        # 3. Sources
        cur.execute("""
        CREATE TABLE IF NOT EXISTS sources (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            source_url TEXT NOT NULL,
            source_type TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            last_checked_at TEXT,
            UNIQUE(entity_id, source_url)
        )
        """)

        # 4. Documents
        cur.execute("""
        CREATE TABLE IF NOT EXISTS documents (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            source_id TEXT NOT NULL REFERENCES sources(id) ON DELETE CASCADE,
            source_url TEXT NOT NULL,
            raw_snapshot_ref TEXT NOT NULL,
            content_hash TEXT NOT NULL,
            extracted_text TEXT NOT NULL,
            language TEXT NOT NULL DEFAULT 'en',
            published_at TEXT,
            fetched_at TEXT NOT NULL,
            fetch_status TEXT NOT NULL,
            UNIQUE(entity_id, content_hash)
        )
        """)

        # 5. Claims
        cur.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
            claim_type TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            raw_excerpt TEXT NOT NULL,
            excerpt_char_start INTEGER NOT NULL,
            excerpt_char_end INTEGER NOT NULL,
            extraction_confidence REAL NOT NULL,
            extractor_model_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            effective_date TEXT
        )
        """)
        try:
            cur.execute("ALTER TABLE claims ADD COLUMN effective_date TEXT")
        except Exception:
            pass

        # 6. Comparisons
        cur.execute("""
        CREATE TABLE IF NOT EXISTS comparisons (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            claim_a_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            claim_b_id TEXT NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
            verdict TEXT NOT NULL,
            confidence REAL NOT NULL,
            reasoning TEXT NOT NULL,
            requires_human_review INTEGER NOT NULL DEFAULT 0,
            reasoner_model_version TEXT NOT NULL,
            created_at TEXT NOT NULL,
            impact_level TEXT DEFAULT 'HIGH',
            impact_score REAL DEFAULT 0.8,
            impact_category TEXT DEFAULT 'Eligibility & Exclusion',
            impact_summary TEXT DEFAULT '',
            priority_rank REAL DEFAULT 0.8,
            UNIQUE(claim_a_id, claim_b_id)
        )
        """)
        # Run migrations for comparisons table if new impact columns are missing
        for col_name, col_type in [
            ("impact_level", "TEXT DEFAULT 'HIGH'"),
            ("impact_score", "REAL DEFAULT 0.8"),
            ("impact_category", "TEXT DEFAULT 'Eligibility & Exclusion'"),
            ("impact_summary", "TEXT DEFAULT ''"),
            ("priority_rank", "REAL DEFAULT 0.8"),
        ]:
            try:
                cur.execute(f"ALTER TABLE comparisons ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        # 7. Review Actions
        cur.execute("""
        CREATE TABLE IF NOT EXISTS review_actions (
            id TEXT PRIMARY KEY,
            comparison_id TEXT NOT NULL REFERENCES comparisons(id) ON DELETE CASCADE,
            reviewer_id TEXT NOT NULL,
            action TEXT NOT NULL,
            notes TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 8. Retrieval Failures
        cur.execute("""
        CREATE TABLE IF NOT EXISTS retrieval_failures (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            source_url TEXT NOT NULL,
            reason_code TEXT NOT NULL,
            occurred_at TEXT NOT NULL,
            fallback_used INTEGER NOT NULL DEFAULT 0,
            fallback_document_id TEXT
        )
        """)

        # 9. Eval Cases
        cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_cases (
            id TEXT PRIMARY KEY,
            claim_a_excerpt TEXT NOT NULL,
            claim_b_excerpt TEXT NOT NULL,
            claim_type TEXT NOT NULL,
            human_label TEXT NOT NULL,
            notes TEXT,
            source_review_id TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 10. Eval Runs
        cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_runs (
            id TEXT PRIMARY KEY,
            run_at TEXT NOT NULL,
            extractor_model_version TEXT NOT NULL,
            reasoner_model_version TEXT NOT NULL,
            prompt_version_hash TEXT NOT NULL,
            total_cases INTEGER NOT NULL,
            accuracy REAL NOT NULL,
            false_positive_rate REAL NOT NULL,
            false_negative_rate REAL NOT NULL,
            promoted_to_production INTEGER NOT NULL DEFAULT 0
        )
        """)

        # 11. Eval Case Results
        cur.execute("""
        CREATE TABLE IF NOT EXISTS eval_case_results (
            id TEXT PRIMARY KEY,
            eval_run_id TEXT NOT NULL REFERENCES eval_runs(id) ON DELETE CASCADE,
            eval_case_id TEXT NOT NULL REFERENCES eval_cases(id) ON DELETE CASCADE,
            model_label TEXT NOT NULL,
            model_confidence REAL NOT NULL,
            correct INTEGER NOT NULL,
            UNIQUE(eval_run_id, eval_case_id)
        )
        """)

        # 12. Cost Ledger
        cur.execute("""
        CREATE TABLE IF NOT EXISTS cost_ledger (
            id TEXT PRIMARY KEY,
            entity_id TEXT,
            stage TEXT NOT NULL,
            tokens_in INTEGER NOT NULL,
            tokens_out INTEGER NOT NULL,
            cost_usd REAL NOT NULL,
            created_at TEXT NOT NULL
        )
        """)

        # 13. Audit Log
        cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id TEXT PRIMARY KEY,
            actor_type TEXT NOT NULL,
            actor_id TEXT,
            action TEXT NOT NULL,
            target_entity_type TEXT NOT NULL,
            target_entity_id TEXT,
            payload TEXT,
            created_at TEXT NOT NULL
        )
        """)

        # 14. User Search & Investigation History
        cur.execute("""
        CREATE TABLE IF NOT EXISTS user_search_history (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
            entity_name TEXT NOT NULL,
            contradiction_count INTEGER NOT NULL DEFAULT 0,
            comparison_count INTEGER NOT NULL DEFAULT 0,
            searched_at TEXT NOT NULL
        )
        """)

        # Create default admin user if not exists
        cur.execute("SELECT id FROM users WHERE email = 'auditor@autopsy.ai'")
        if not cur.fetchone():
            cur.execute("""
            INSERT INTO users (id, email, display_name, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """, (str(uuid.uuid4()), "auditor@autopsy.ai", "Policy Auditor", "auditor", datetime.datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

    def log_cost(self, entity_id: Optional[str], stage: str, tokens_in: int, tokens_out: int, cost_usd: float):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO cost_ledger (id, entity_id, stage, tokens_in, tokens_out, cost_usd, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), entity_id, stage, tokens_in, tokens_out, cost_usd, datetime.datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    def log_audit(self, actor_type: str, actor_id: Optional[str], action: str, target_table: str, target_id: str, payload: Optional[dict] = None):
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO audit_log (id, actor_type, actor_id, action, target_table, target_id, payload, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (str(uuid.uuid4()), actor_type, actor_id, action, target_table, target_id, json.dumps(payload) if payload else None, datetime.datetime.utcnow().isoformat()))
        conn.commit()
        conn.close()

    def get_cost_summary(self) -> Dict[str, Any]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT stage, SUM(tokens_in) as total_tokens_in, SUM(tokens_out) as total_tokens_out, SUM(cost_usd) as total_cost_usd, COUNT(*) as call_count
        FROM cost_ledger
        GROUP BY stage
        """)
        stage_rows = cur.fetchall()
        cur.execute("SELECT SUM(cost_usd) as grand_total_usd, SUM(tokens_in + tokens_out) as grand_total_tokens FROM cost_ledger")
        grand_row = cur.fetchone()
        conn.close()
        
        stages = [dict(r) for r in stage_rows]
        return {
            "grand_total_usd": round(grand_row["grand_total_usd"] or 0.0, 4),
            "grand_total_tokens": grand_row["grand_total_tokens"] or 0,
            "stages": stages
        }

db = Database()
