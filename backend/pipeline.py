import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from backend.config import BACKEND_DIR, is_live_ready, is_tinyfish_configured, is_groq_configured
from backend.models import Source, ExtractedFact, Finding, ReviewAction
from backend.quote_verifier import verify_quote
from backend.gap_engine import evaluate_all_facts
from backend.tinyfish_client import TinyFishClient
from backend.extractor import ReliefExtractor

logger = logging.getLogger(__name__)

MOCK_DATA_PATH = BACKEND_DIR / "mock_data.json"

class ReliefPipeline:
    def __init__(self, db: Session):
        self.db = db
        self.tinyfish = TinyFishClient()
        self.extractor = ReliefExtractor()

    def clear_database(self):
        """Clears all findings, facts, sources, and review actions."""
        self.db.query(ReviewAction).delete()
        self.db.query(Finding).delete()
        self.db.query(ExtractedFact).delete()
        self.db.query(Source).delete()
        self.db.commit()

    def load_demo_data(self) -> Dict[str, Any]:
        """
        Loads the high-fidelity South Odisha Cyclone synthetic dataset.
        Executes strict quote verification for every record.
        Synthetic records are explicitly marked `is_synthetic = True`.
        """
        if not MOCK_DATA_PATH.exists():
            raise FileNotFoundError(f"Mock data file not found at {MOCK_DATA_PATH}")

        with open(MOCK_DATA_PATH, "r", encoding="utf-8") as f:
            demo = json.load(f)

        self.clear_database()

        url_to_source = {}
        for s_data in demo.get("sources", []):
            source = Source(
                url=s_data["url"],
                title=s_data.get("title", ""),
                snippet=s_data.get("snippet", ""),
                text=s_data.get("text", ""),
                fetch_status=s_data.get("fetch_status", "SUCCESS"),
                error_msg=s_data.get("error_msg", ""),
                is_synthetic=True
            )
            self.db.add(source)
            self.db.flush()
            url_to_source[s_data["url"]] = source

        # Process facts and run Quote Verifier
        verified_count = 0
        rejected_count = 0
        raw_fact_objs = []

        for f_data in demo.get("facts", []):
            src = url_to_source.get(f_data.get("source_url"))
            src_text = src.text if src else ""
            quote = f_data.get("evidence_quote", "")

            # Exact quote verification
            is_valid, msg = verify_quote(src_text, quote)
            if is_valid:
                verified_count += 1
            else:
                rejected_count += 1

            fact = ExtractedFact(
                source_id=src.id if src else None,
                location=f_data["location"],
                district=f_data["district"],
                item=f_data["item"],
                record_type=f_data["record_type"],
                quantity=f_data.get("quantity"),
                unit=f_data.get("unit"),
                urgency=f_data.get("urgency", "UNKNOWN"),
                report_date=f_data.get("report_date"),
                evidence_quote=quote,
                is_verified=is_valid,
                verification_notes=msg,
                is_synthetic=True
            )
            self.db.add(fact)
            self.db.flush()
            raw_fact_objs.append(fact)

        # Build dictionary representation of facts for GapEngine
        facts_payload = [
            {
                "id": f.id,
                "location": f.location,
                "district": f.district,
                "item": f.item,
                "record_type": f.record_type,
                "quantity": f.quantity,
                "unit": f.unit,
                "urgency": f.urgency,
                "report_date": f.report_date,
                "evidence_quote": f.evidence_quote,
                "is_verified": f.is_verified
            }
            for f in raw_fact_objs
        ]

        # Run Deterministic Gap Engine
        findings_data = evaluate_all_facts(facts_payload)

        for fd in findings_data:
            finding = Finding(
                district=fd["district"],
                location=fd["location"],
                item=fd["item"],
                classification=fd["classification"],
                priority=fd["priority"],
                reasoning=fd["reasoning"],
                need_fact_id=fd["need_fact_id"],
                supply_fact_id=fd["supply_fact_id"],
                conflict_fact_id=fd["conflict_fact_id"],
                partial_percentage=fd["partial_percentage"],
                review_status="PENDING",
                is_synthetic=True
            )
            self.db.add(finding)

        self.db.commit()

        return {
            "status": "success",
            "mode": "DEMO (SYNTHETIC DATA)",
            "sources_loaded": len(url_to_source),
            "facts_extracted": len(demo.get("facts", [])),
            "verified_quotes": verified_count,
            "rejected_quotes": rejected_count,
            "findings_generated": len(findings_data),
            "disaster": demo.get("event_name", "South Odisha Cyclone Relief")
        }

    def run_live_scan(self, district: str = "Ganjam", custom_query: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes LIVE MODE pipeline:
        1. Checks configuration (no silent fallback).
        2. TinyFish Search discovering sources for the district.
        3. TinyFish Fetch retrieving cleaned markdown.
        4. Groq extracting structured facts.
        5. Quote Verifier checking substrings.
        6. Gap Engine classifying findings.
        """
        if not is_tinyfish_configured():
            raise ValueError(
                "TINYFISH_API_KEY is not set or invalid. "
                "Configure your API key in the .env file to run in LIVE MODE."
            )

        if not is_groq_configured():
            raise ValueError(
                "GROQ_API_KEY is not set or invalid. "
                "Configure your API key in the .env file to run in LIVE MODE."
            )

        # 1. Search Query
        query = custom_query or f"{district} Odisha cyclone flood relief drinking water medical food situation report"
        search_results = self.tinyfish.search(query, recency_minutes=None, max_results=4)

        if not search_results:
            return {
                "status": "completed",
                "mode": "LIVE",
                "message": f"No search results returned by TinyFish for query: '{query}'",
                "sources_discovered": 0,
                "sources_fetched": 0,
                "facts_extracted": 0,
                "findings_generated": 0
            }

        discovered_urls = [r["url"] for r in search_results]
        saved_sources = []

        # 2. Fetch URLs
        for sr in search_results:
            url = sr["url"]
            # Check if source already in DB
            existing_source = self.db.query(Source).filter(Source.url == url).first()
            if existing_source and existing_source.fetch_status == "SUCCESS":
                fetch_res = {
                    "url": existing_source.url,
                    "title": existing_source.title,
                    "text": existing_source.text,
                    "fetch_status": existing_source.fetch_status,
                    "error_msg": existing_source.error_msg
                }
                src_obj = existing_source
            else:
                fetch_res = self.tinyfish.fetch_url(url)
                if existing_source:
                    existing_source.title = fetch_res.get("title", sr.get("title", ""))
                    existing_source.text = fetch_res.get("text", "")
                    existing_source.fetch_status = fetch_res.get("fetch_status", "FAILED")
                    existing_source.error_msg = fetch_res.get("error_msg", "")
                    existing_source.is_synthetic = False
                    src_obj = existing_source
                else:
                    src_obj = Source(
                        url=url,
                        title=fetch_res.get("title", sr.get("title", "")),
                        snippet=sr.get("snippet", ""),
                        text=fetch_res.get("text", ""),
                        fetch_status=fetch_res.get("fetch_status", "FAILED"),
                        error_msg=fetch_res.get("error_msg", ""),
                        is_synthetic=False
                    )
                    self.db.add(src_obj)
                self.db.flush()

            saved_sources.append(src_obj)

        # 3. Extract Facts from successful fetches
        extracted_facts_records = []
        verified_count = 0
        rejected_count = 0

        for src in saved_sources:
            if src.fetch_status != "SUCCESS" or not src.text:
                continue

            try:
                raw_extracted = self.extractor.extract_facts_from_text(
                    source_text=src.text,
                    source_url=src.url,
                    source_title=src.title,
                    district_hint=district
                )

                for f_item in raw_extracted:
                    quote = f_item.get("evidence_quote", "")
                    is_valid, msg = verify_quote(src.text, quote)

                    if is_valid:
                        verified_count += 1
                    else:
                        rejected_count += 1

                    fact_obj = ExtractedFact(
                        source_id=src.id,
                        location=f_item["location"],
                        district=f_item.get("district", district),
                        item=f_item["item"],
                        record_type=f_item["record_type"],
                        quantity=f_item.get("quantity"),
                        unit=f_item.get("unit"),
                        urgency=f_item.get("urgency", "UNKNOWN"),
                        report_date=f_item.get("report_date"),
                        evidence_quote=quote,
                        is_verified=is_valid,
                        verification_notes=msg,
                        is_synthetic=False
                    )
                    self.db.add(fact_obj)
                    self.db.flush()
                    extracted_facts_records.append(fact_obj)

            except Exception as e:
                logger.error(f"Error extracting from {src.url}: {e}")

        # 4. Deterministic Gap Engine
        facts_payload = [
            {
                "id": f.id,
                "location": f.location,
                "district": f.district,
                "item": f.item,
                "record_type": f.record_type,
                "quantity": f.quantity,
                "unit": f.unit,
                "urgency": f.urgency,
                "report_date": f.report_date,
                "evidence_quote": f.evidence_quote,
                "is_verified": f.is_verified
            }
            for f in extracted_facts_records
        ]

        new_findings = evaluate_all_facts(facts_payload)

        for fd in new_findings:
            finding = Finding(
                district=fd["district"],
                location=fd["location"],
                item=fd["item"],
                classification=fd["classification"],
                priority=fd["priority"],
                reasoning=fd["reasoning"],
                need_fact_id=fd["need_fact_id"],
                supply_fact_id=fd["supply_fact_id"],
                conflict_fact_id=fd["conflict_fact_id"],
                partial_percentage=fd["partial_percentage"],
                review_status="PENDING",
                is_synthetic=False
            )
            self.db.add(finding)

        self.db.commit()

        return {
            "status": "success",
            "mode": "LIVE",
            "sources_discovered": len(discovered_urls),
            "sources_fetched": sum(1 for s in saved_sources if s.fetch_status == "SUCCESS"),
            "facts_extracted": len(extracted_facts_records),
            "verified_quotes": verified_count,
            "rejected_quotes": rejected_count,
            "findings_generated": len(new_findings)
        }
