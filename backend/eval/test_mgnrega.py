import asyncio
import logging
logging.basicConfig(level=logging.INFO)

from backend.engine.wikipedia_agent import WikipediaRetrievalAgent
from backend.engine.extractor_engine import ExtractorEngine
from backend.engine.drift_reasoning_engine import DriftReasoningEngine, ClaimForComparison

async def test_mgnrega():
    wiki = WikipediaRetrievalAgent()
    docs = await wiki.fetch_documents_for_entity("MGNREGA")
    print(f"Total docs retrieved: {len(docs)}")
    
    extractor = ExtractorEngine()
    all_claims = []
    
    for i, d in enumerate(docs):
        claims = await extractor.extract(f"doc_{i}", d["text"])
        print(f"\nDocument {i} ({d.get('published_at')} | {d.get('url')}): {len(claims)} claims")
        for c in claims:
            print(f"  - [{c.claim_type}] (conf: {c.extraction_confidence}): {c.raw_excerpt[:100]}")
            all_claims.append(ClaimForComparison(
                claim_id=c.id,
                raw_excerpt=c.raw_excerpt,
                normalized_value=c.normalized_value,
                published_at=d.get("published_at"),
                source_url=d.get("url")
            ))
            
    print(f"\nTotal claims for comparison: {len(all_claims)}")
    reasoner = DriftReasoningEngine()
    pairs = reasoner.build_comparison_pairs(all_claims)
    print(f"Total pairs formed: {len(pairs)}")
    
    for ca, cb in pairs[:5]:
        res = await reasoner.compare(ca, cb)
        print(f"\n--- PAIR RESULT ---")
        print(f"Verdict: {res.verdict} (conf: {res.calibrated_confidence})")
        print(f"Claim A ({ca.published_at}): {ca.raw_excerpt[:80]}")
        print(f"Claim B ({cb.published_at}): {cb.raw_excerpt[:80]}")
        print(f"Reasoning: {res.reasoning}")

if __name__ == "__main__":
    asyncio.run(test_mgnrega())
