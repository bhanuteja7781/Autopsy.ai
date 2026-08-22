"""
WikipediaRetrievalAgent — Live multi-era historical ingestion from Wikipedia's open APIs.

Strategy:
  1. Search Wikipedia for the exact entity / scheme name -> get the best matching article title.
  2. Fetch the article's CURRENT version (with real timestamp and text).
  3. Fetch historical revisions sampled across distinct years (e.g. 2026, 2023, 2019, 2014, 2008)
     so the Drift Reasoner has genuine chronological documents across the policy's lifespan.
  4. Strip wikitext cleanly to plain readable paragraphs focusing on statutory provisions,
     eligibility rules, amounts, deadlines, and amendments.
"""
from __future__ import annotations
import hashlib
import asyncio
import logging
import re
import uuid
import datetime
from typing import Optional, List, Dict, Any

import httpx

logger = logging.getLogger("wikipedia_agent")

WIKI_API = "https://en.wikipedia.org/w/api.php"
WIKI_REST = "https://en.wikipedia.org/api/rest_v1"
HEADERS = {"User-Agent": "AutopsyPolicyAuditor/2.0 (civictech@autopsy.ai; public policy research)"}


class WikipediaRetrievalAgent:
    """
    Fetches real, dated Wikipedia article snapshots across distinct years for any scheme/policy.
    """

    def __init__(self, http_client: Optional[httpx.AsyncClient] = None):
        # Wikipedia requires a distinct informative User-Agent; ensure headers are applied
        self.http = http_client or httpx.AsyncClient(headers=HEADERS, timeout=10.0)

    async def fetch_documents_for_entity(self, entity_name: str, max_eras: int = 4) -> list[dict]:
        """
        Returns a chronological list of document dicts with keys:
          text, url, published_at, fetch_status, source_title
        """
        try:
            article_title = await self._search_article(entity_name)
            if not article_title:
                logger.warning("Wikipedia: no article found for '%s'", entity_name)
                return []

            logger.info("Wikipedia: matched article '%s' for '%s'", article_title, entity_name)
            docs: list[dict] = []

            # 1. Fetch multi-era historical snapshots (sampling across years)
            eras = ["2026-01-01T00:00:00Z", "2023-01-01T00:00:00Z", "2019-01-01T00:00:00Z", "2014-01-01T00:00:00Z", "2008-01-01T00:00:00Z"]
            seen_hashes = set()

            for era_date in eras[:max_eras + 1]:
                rev_doc = await self._fetch_era_revision(article_title, era_date)
                if rev_doc:
                    chash = hashlib.sha256(rev_doc["text"].encode("utf-8")).hexdigest()
                    if chash not in seen_hashes:
                        seen_hashes.add(chash)
                        docs.append(rev_doc)

            # If multi-era failed or returned < 2, fallback to recent revisions
            if len(docs) < 2:
                recent = await self._fetch_recent_revisions(article_title, limit=3)
                for r in recent:
                    chash = hashlib.sha256(r["text"].encode("utf-8")).hexdigest()
                    if chash not in seen_hashes:
                        seen_hashes.add(chash)
                        docs.append(r)

            # If still only 0 or 1, fetch current summary
            if len(docs) == 0:
                current = await self._fetch_current_summary(article_title)
                if current:
                    docs.append(current)

            # Sort chronologically by published_at
            docs.sort(key=lambda d: d.get("published_at", ""))
            return docs

        except Exception as exc:
            logger.error("WikipediaRetrievalAgent error for '%s': %s", entity_name, exc)
            return []

    async def _search_article(self, query: str) -> Optional[str]:
        """Search Wikipedia for the most relevant article title."""
        queries_to_try = [query]
        clean_q = re.sub(r'[^a-zA-Z0-9\s]', ' ', query).strip()
        if clean_q != query:
            queries_to_try.append(clean_q)

        # Add common aliases for known Indian schemes / terms
        low = query.lower()
        if "garib" in low and "awaas" in low:
            queries_to_try.extend(["Pradhan Mantri Gramin Awas Yojana", "Pradhan Mantri Awas Yojana"])
        elif "mgnrega" in low or "nrega" in low:
            queries_to_try.append("Mahatma Gandhi National Rural Employment Guarantee Act, 2005")
        elif "kisan" in low:
            queries_to_try.append("PM-KISAN")
        elif "ayushman" in low:
            queries_to_try.append("Ayushman Bharat Yojana")

        for q in queries_to_try:
            try:
                resp = await self.http.get(
                    WIKI_API,
                    params={
                        "action": "query",
                        "list": "search",
                        "srsearch": q,
                        "srlimit": 3,
                        "srnamespace": 0,
                        "format": "json",
                    },
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    results = data.get("query", {}).get("search", [])
                    if results:
                        return results[0]["title"]
            except Exception as e:
                logger.debug("Wikipedia search error for '%s': %s", q, e)
        return None

    async def _fetch_era_revision(self, article_title: str, start_timestamp: str) -> Optional[dict]:
        """Fetch the revision of an article as it existed at or before a given timestamp."""
        try:
            resp = await self.http.get(
                WIKI_API,
                params={
                    "action": "query",
                    "prop": "revisions",
                    "titles": article_title,
                    "rvprop": "ids|timestamp|content",
                    "rvslots": "main",
                    "rvstart": start_timestamp,
                    "rvlimit": 1,
                    "rvdir": "older",
                    "format": "json",
                    "formatversion": "2",
                },
                timeout=10.0,
            )
            if resp.status_code != 200:
                return None

            pages = resp.json().get("query", {}).get("pages", [])
            if not pages or not pages[0].get("revisions"):
                return None

            rev = pages[0]["revisions"][0]
            ts = rev.get("timestamp", "")
            revid = rev.get("revid", "")
            wikitext = rev.get("slots", {}).get("main", {}).get("content", "")
            if not wikitext or len(wikitext) < 100:
                return None

            clean_text = self._strip_wikitext(wikitext)
            if len(clean_text) < 80:
                return None

            # Keep focused text (up to 3500 chars) highlighting statutory provisions & claims
            clean_text = clean_text[:3500].strip()
            published_at = ts[:10] if ts else start_timestamp[:10]
            page_url = f"https://en.wikipedia.org/w/index.php?title={article_title.replace(' ', '_')}&oldid={revid}"

            return {
                "text": clean_text,
                "url": page_url,
                "published_at": published_at,
                "fetch_status": "success",
                "source_title": f"{article_title} (Archived {published_at})"
            }
        except Exception as exc:
            logger.debug("Wikipedia era revision fetch failed: %s", exc)
            return None

    async def _fetch_recent_revisions(self, article_title: str, limit: int = 3) -> list[dict]:
        """Fetch most recent revisions."""
        try:
            resp = await self.http.get(
                WIKI_API,
                params={
                    "action": "query",
                    "prop": "revisions",
                    "titles": article_title,
                    "rvprop": "ids|timestamp|content",
                    "rvlimit": limit + 2,
                    "rvslots": "main",
                    "rvdir": "older",
                    "format": "json",
                    "formatversion": "2",
                },
                timeout=10.0,
            )
            if resp.status_code != 200:
                return []

            pages = resp.json().get("query", {}).get("pages", [])
            if not pages or not pages[0].get("revisions"):
                return []

            revisions = pages[0].get("revisions", [])
            docs = []

            for rev in revisions:
                ts = rev.get("timestamp", "")
                published_at = ts[:10] if ts else "2024-01-01"
                revid = rev.get("revid", "")
                wikitext = rev.get("slots", {}).get("main", {}).get("content", "")
                if not wikitext:
                    continue

                clean = self._strip_wikitext(wikitext)
                if len(clean) < 80:
                    continue

                clean = clean[:3500].strip()
                page_url = f"https://en.wikipedia.org/w/index.php?title={article_title.replace(' ', '_')}&oldid={revid}"
                docs.append({
                    "text": clean,
                    "url": page_url,
                    "published_at": published_at,
                    "fetch_status": "success",
                    "source_title": f"{article_title} (Revision {published_at})"
                })
                if len(docs) >= limit:
                    break

            return docs
        except Exception:
            return []

    async def _fetch_current_summary(self, article_title: str) -> Optional[dict]:
        """Fetch current summary via REST API."""
        try:
            resp = await self.http.get(
                f"{WIKI_REST}/page/summary/{article_title.replace(' ', '_')}",
                timeout=10.0,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            extract = data.get("extract", "")
            if len(extract) < 50:
                return None

            page_url = data.get("content_urls", {}).get("desktop", {}).get("page", f"https://en.wikipedia.org/wiki/{article_title.replace(' ', '_')}")
            timestamp = data.get("timestamp", "")
            published_at = timestamp[:10] if timestamp else datetime.date.today().isoformat()

            return {
                "text": extract,
                "url": page_url,
                "published_at": published_at,
                "fetch_status": "success",
                "source_title": f"{article_title} (Current)"
            }
        except Exception:
            return None

    def _strip_wikitext(self, wikitext: str) -> str:
        """Thoroughly strip wikitext markup to produce clean, sentence-structured plain text."""
        # 1. Strip comments
        text = re.sub(r'<!--.*?-->', '', wikitext, flags=re.DOTALL)
        # 2. Strip templates recursively (up to 3 passes for nested templates)
        for _ in range(3):
            text = re.sub(r'\{\{[^{}]*\}\}', '', text, flags=re.DOTALL)
        # 3. Strip tables
        text = re.sub(r'\{\|.*?\|\}', '', text, flags=re.DOTALL)
        # 4. Strip refs
        text = re.sub(r'<ref[^>]*>.*?</ref>', '', text, flags=re.DOTALL)
        text = re.sub(r'<ref[^/]*/>', '', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        # 5. Strip file/image links
        text = re.sub(r'\[\[(File|Image|Category):[^\]]*\]\]', '', text, flags=re.IGNORECASE)
        # 6. Simplify internal links: [[target|label]] -> label, [[target]] -> target
        text = re.sub(r'\[\[(?:[^|\]]*\|)?([^\]]+)\]\]', r'\1', text)
        # 7. Strip external links: [http... label] -> label or empty
        text = re.sub(r'\[https?://[^\s\]]+\s*([^\]]*)\]', r'\1', text)
        text = re.sub(r'https?://\S+', '', text)
        # 8. Clean section headings: == Heading == -> Heading.
        text = re.sub(r'={2,}([^=]+)={2,}', r'. \1. ', text)
        # 9. Clean quotes and formatting
        text = re.sub(r"'{2,}", '', text)
        text = re.sub(r'[*#:;]', ' ', text)
        # 10. Normalize whitespace and punctuation
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'\s*\.\s*', '. ', text)
        text = re.sub(r'\.{2,}', '.', text)
        return text.strip()
