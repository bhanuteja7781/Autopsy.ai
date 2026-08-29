from __future__ import annotations
import hashlib
import asyncio
import logging
import uuid
import datetime
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional, List

import httpx
from bs4 import BeautifulSoup
from backend.core.db import db
from backend.core.config import settings

logger = logging.getLogger("retrieval_agent")

CACHE_TTL_SECONDS = 60 * 60 * 6  # 6 hours
MAX_RETRIES = 2
BASE_BACKOFF_SECONDS = 0.8


@dataclass
class FetchedDocument:
    id: str
    source_url: str
    raw_content: bytes
    extracted_text: str
    content_hash: str
    fetched_at: str
    published_at_guess: Optional[str]
    fetch_status: str  # 'success' | 'failed'


def build_targeted_search_queries(entity_name: str) -> list[str]:
    """
    Constructs clean, dynamic search queries tailored strictly to the user's entity.
    Retrieves baseline statutory foundation as well as subsequent amendments/rules.
    Zero hardcoded policy names or acronym assumptions.
    """
    clean_name = entity_name.strip()
    return [
        f"{clean_name} official policy rules guidelines gazette notification",
        f"{clean_name} official rules amendment revision updates gazette",
    ]


class RetrievalAgent:
    """
    Live scraping and processing pipeline.
    Retrieves current web evidence through Tavily only.
    Any missing key, failed request, or empty result is an error.
    """

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        self.http = http_client or httpx.AsyncClient(
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                )
            },
            timeout=10.0,
        )

    async def retrieve_for_entity(
        self, entity_id: str, entity_name: str
    ) -> list[FetchedDocument]:
        """
        Main live retrieval pipeline.
        Raises RuntimeError when Tavily cannot return usable documents.
        """
        print(f"[Scraper] Fetching live documents for query: '{entity_name}'...")
        logger.info(
            "[Scraper] Starting live retrieval pipeline for entity '%s' (id=%s)...",
            entity_name,
            entity_id,
        )

        # Dynamic targeted multi-perspective query expansion
        queries = build_targeted_search_queries(entity_name)
        results = await self._execute_live_web_search(
            entity_id, entity_name, queries
        )

        # Sort chronologically
        results.sort(key=lambda d: d.published_at_guess or d.fetched_at)

        # Persist
        await self._persist_documents(entity_id, results)
        total_chars = sum(len(d.extracted_text) for d in results)
        est_tokens = max(50, total_chars // 4)
        db.log_cost(
            entity_id,
            "retrieval",
            tokens_in=est_tokens,
            tokens_out=0,
            cost_usd=round(est_tokens * 0.000002 + 0.005, 4),
        )
        db.log_audit(
            "system",
            None,
            "retrieval_completed",
            "documents",
            entity_id,
            {"documents_retrieved": len(results)},
        )
        print(f"[Scraper] Retrieved {len(results)} live documents for query: '{entity_name}'")
        return results

    # ── Search Backends ───────────────────────────────────────────────────────

    async def _execute_live_web_search(
        self, entity_id: str, entity_name: str, search_queries: list[str]
    ) -> list[FetchedDocument]:
        """Runs parallel live Tavily searches across baseline and contemporary amendment queries."""
        if not settings.TAVILY_API_KEY:
            raise RuntimeError("TAVILY_API_KEY is not configured.")

        docs: list[FetchedDocument] = []
        seen_urls: set[str] = set()

        async def _fetch_query(query: str) -> list[FetchedDocument]:
            try:
                resp = await self.http.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": settings.TAVILY_API_KEY,
                        "query": query,
                        "search_depth": "advanced",
                        "include_raw_content": True,
                        "max_results": 10,
                        "exclude_domains": ["youtube.com", "facebook.com", "x.com", "twitter.com", "instagram.com"]
                    },
                    timeout=15.0,
                )
                if resp.status_code != 200:
                    logger.warning("Tavily query failed with HTTP %d: %s", resp.status_code, resp.text[:300])
                    return []

                data = resp.json()
                local_docs: list[FetchedDocument] = []
                for item in data.get("results", []):
                    raw_text = item.get("raw_content") or ""
                    clean = self._clean_text(raw_text) if raw_text else ""
                    if len(clean) < 100 and item.get("content"):
                        clean = self._clean_text(item.get("content", "")) or item.get("content", "")

                    if len(clean) >= 60:
                        clean = clean[:3000].strip()
                        url = item.get("url", "")
                        chash = hashlib.sha256(clean.encode("utf-8")).hexdigest()
                        pub_date = item.get("published_date") or item.get("published_at")
                        local_docs.append(
                            FetchedDocument(
                                id=str(uuid.uuid4()),
                                source_url=url,
                                raw_content=clean.encode("utf-8"),
                                extracted_text=clean,
                                content_hash=chash,
                                fetched_at=datetime.datetime.now(
                                    datetime.timezone.utc
                                ).isoformat(),
                                published_at_guess=pub_date,
                                fetch_status="success",
                            )
                        )
                return local_docs
            except Exception as exc:
                logger.warning("Tavily search exception for query '%s': %s", query, exc)
                return []

        query_results = await asyncio.gather(*[_fetch_query(q) for q in search_queries])
        for q_docs in query_results:
            for d in q_docs:
                if d.source_url not in seen_urls:
                    seen_urls.add(d.source_url)
                    docs.append(d)

        if not docs:
            if timed_out:
                raise RuntimeError("Retrieval timed out. Please retry.")
            raise RuntimeError(f"Tavily returned no usable documents for '{entity_name}'.")
        logger.info("[Tavily] Returned %d usable documents.", len(docs))
        return docs[:8]

    async def _search_duckduckgo(self, query: str) -> list[str]:
        """Search DuckDuckGo HTML for policy-related pages."""
        urls: list[str] = []
        try:
            resp = await self.http.get(
                f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}",
                timeout=10.0,
            )
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, "html.parser")
                for a in soup.select("a.result__url"):
                    href = a.get("href", "")
                    if "uddg=" in href:
                        parsed = urllib.parse.parse_qs(
                            urllib.parse.urlparse(href).query
                        )
                        actual = parsed.get("uddg", [""])[0]
                        if actual and actual.startswith("http") and not actual.endswith(".pdf"):
                            urls.append(actual)
                    elif href.startswith("http") and not href.endswith(".pdf"):
                        urls.append(href)
        except Exception as exc:
            logger.debug("DuckDuckGo search error: %s", exc)
        return urls[:5]

    async def _fetch_candidate_urls(
        self, entity_id: str, candidate_urls: list[str]
    ) -> list[FetchedDocument]:
        if not candidate_urls:
            return []

        async def _fetch_safe(url: str) -> Optional[FetchedDocument]:
            try:
                return await asyncio.wait_for(
                    self._fetch_with_retry(entity_id, url), timeout=10.0
                )
            except Exception as exc:
                logger.warning("Dropping timed-out or failed target %s: %s", url, exc)
                return None

        fetch_tasks = [_fetch_safe(url) for url in candidate_urls]
        fetched = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        results = []
        for item in fetched:
            if (
                isinstance(item, FetchedDocument)
                and item is not None
                and len(item.extracted_text) > 80
            ):
                results.append(item)
        return results

    async def _fetch_with_retry(
        self, entity_id: str, url: str
    ) -> Optional[FetchedDocument]:
        for attempt in range(MAX_RETRIES):
            try:
                response = await self.http.get(url, timeout=10.0, follow_redirects=True)
                if response.status_code >= 400:
                    await self._log_failure(entity_id, url, reason_code="http_error")
                    return None

                raw_content = response.content
                if not raw_content:
                    await self._log_failure(entity_id, url, reason_code="empty_body")
                    return None

                extracted_text = self._clean_text(response.text)
                if len(extracted_text) < 60:
                    await self._log_failure(entity_id, url, reason_code="parse_error")
                    return None

                extracted_text = extracted_text[:3500].strip()
                content_hash = hashlib.sha256(raw_content).hexdigest()
                doc_id = str(uuid.uuid4())
                pub_date = self._guess_publish_date(extracted_text)

                return FetchedDocument(
                    id=doc_id,
                    source_url=url,
                    raw_content=raw_content,
                    extracted_text=extracted_text,
                    content_hash=content_hash,
                    fetched_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    published_at_guess=pub_date,
                    fetch_status="success",
                )

            except (httpx.TimeoutException, httpx.ConnectError, asyncio.TimeoutError) as exc:
                logger.warning("Dropping timed-out or failed target %s: %s", url, exc)
                await self._log_failure(entity_id, url, reason_code="timeout")
                return None
            except Exception:
                await self._log_failure(entity_id, url, reason_code="other")
                return None

        await self._log_failure(entity_id, url, reason_code="timeout")
        return None

    async def _search_pib_archives(
        self, entity_id: str, entity_name: str
    ) -> list[FetchedDocument]:
        docs: list[FetchedDocument] = []
        try:
            query = f"{entity_name} site:pib.gov.in"
            urls = await self._search_duckduckgo(query)
            if urls:
                docs = await self._fetch_candidate_urls(entity_id, urls[:3])
        except Exception as e:
            logger.debug("PIB archive search error: %s", e)
        return docs

    # ── Persistence ───────────────────────────────────────────────────────────

    async def _persist_documents(
        self, entity_id: str, docs: list[FetchedDocument]
    ):
        conn = db.get_connection()
        cur = conn.cursor()
        for doc in docs:
            source_id = str(uuid.uuid4())
            cur.execute(
                """
                INSERT OR IGNORE INTO sources (id, entity_id, source_url, source_type, first_seen_at)
                VALUES (?, ?, ?, 'official_release', ?)
                """,
                (
                    source_id,
                    entity_id,
                    doc.source_url,
                    datetime.datetime.now(datetime.timezone.utc).isoformat(),
                ),
            )

            cur.execute(
                "SELECT id FROM sources WHERE entity_id = ? AND source_url = ?",
                (entity_id, doc.source_url),
            )
            src_row = cur.fetchone()
            s_id = src_row["id"] if src_row else source_id

            cur.execute(
                """
                INSERT OR REPLACE INTO documents
                (id, entity_id, source_id, source_url, raw_snapshot_ref, content_hash,
                 extracted_text, published_at, fetched_at, fetch_status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.id,
                    entity_id,
                    s_id,
                    doc.source_url,
                    f"obj_{doc.content_hash}",
                    doc.content_hash,
                    doc.extracted_text,
                    doc.published_at_guess,
                    doc.fetched_at,
                    doc.fetch_status,
                ),
            )
        conn.commit()
        conn.close()

    async def _log_failure(self, entity_id: str, url: str, reason_code: str):
        conn = db.get_connection()
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO retrieval_failures (id, entity_id, source_url, reason_code, occurred_at, fallback_used)
            VALUES (?, ?, ?, ?, ?, 0)
            """,
            (
                str(uuid.uuid4()),
                entity_id,
                url,
                reason_code,
                datetime.datetime.now(datetime.timezone.utc).isoformat(),
            ),
        )
        conn.commit()
        conn.close()

    # ── Utilities ─────────────────────────────────────────────────────────────

    def _guess_publish_date(self, text: str) -> Optional[str]:
        match = re.search(
            r"\b(20\d{2}[-/]\d{2}[-/]\d{2}|"
            r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? 20\d{2})\b",
            text,
            re.IGNORECASE,
        )
        return match.group(0) if match else None

    def _clean_text(self, html_or_text: str) -> str:
        if not html_or_text:
            return ""
        try:
            soup = BeautifulSoup(html_or_text, "html.parser")
            for tag in soup(
                [
                    "script", "style", "nav", "footer", "header", "aside",
                    "form", "button", "iframe", "noscript", "svg",
                ]
            ):
                tag.decompose()
            body = soup.find(["main", "article"]) or soup.body or soup
            for anchor in body.find_all("a"):
                href = (anchor.get("href") or "").lower()
                label = anchor.get_text(" ", strip=True)
                if (
                    href.startswith("#")
                    or "bodycontent" in href
                    or "static/images/" in href
                    or "mw-content-text" in href
                    or re.search(r"jump to|skip to|navigation|menu", label, re.IGNORECASE)
                ):
                    anchor.decompose()
                else:
                    anchor.unwrap()
            paragraphs = body.find_all(["p", "li"], recursive=True)
            if paragraphs:
                text = "\n".join(p.get_text(" ", strip=True) for p in paragraphs)
            else:
                text = body.get_text("\n", strip=True)

            # Tavily may return Markdown even when raw_content is not HTML.
            text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
            text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
            text = re.sub(r"\[[^\]]*\]\([^)]*\)", " ", text)
            text = re.sub(r"https?://\S+", " ", text)

            ui_pattern = (
                r"(?i)^\s*(?:jump to (?:content|search)|skip to (?:content|main content)|"
                r"menu|navigation|search|log in|sign in|register|subscribe|read more|"
                r"view pdf|download pdf|next page|previous page|cookie policy|"
                r"terms of service|privacy policy|disclaimer)\s*$"
            )
            artifact_pattern = re.compile(
                r"(?i)jump\s+to\s+content|skip\s+to\s+(?:content|main)|"
                r"\(#(?:bodycontent|mw-content-text)[^) ]*\)|"
                r"\[/?(?:static/images/|images/)[^\]]*\]|"
                r"^\s*(?:menu|navigation|search|log in|sign in|register|subscribe)\s*$"
            )
            lines = [
                re.sub(r"\s+", " ", line).strip()
                for line in text.splitlines()
                if line.strip() and not re.match(ui_pattern, line) and not artifact_pattern.search(line)
            ]
            return " ".join(lines).strip()
        except Exception:
            return ""
