import io
import csv
import json
from datetime import datetime, timezone
from typing import Optional, List
from fastapi import FastAPI, Depends, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.config import (
    APP_NAME,
    APP_VERSION,
    DEFAULT_DISASTER,
    FRONTEND_DIR,
    is_tinyfish_configured,
    is_groq_configured,
    is_live_ready,
)
from backend.database import get_db, init_db
from backend.models import Source, ExtractedFact, Finding, ReviewAction
from backend.pipeline import ReliefPipeline

# Initialize DB tables on startup
init_db()

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description="ReliefRadar: AI Crisis-Gap Detector and Humanitarian Intelligence System"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------- Pydantic Request Schemas -----------------
class ScanRequest(BaseModel):
    district: str = "Ganjam"
    query: Optional[str] = None
    mode: Optional[str] = "AUTO"  # AUTO, LIVE, DEMO

class ReviewRequest(BaseModel):
    action: str  # APPROVE, REJECT, INVESTIGATE
    notes: Optional[str] = ""

# ----------------- API Endpoints -----------------

@app.get("/api/health")
def get_health(db: Session = Depends(get_db)):
    findings_count = db.query(Finding).count()
    sources_count = db.query(Source).count()
    has_synthetic = db.query(Finding).filter(Finding.is_synthetic == True).first() is not None

    return {
        "status": "healthy",
        "app": APP_NAME,
        "version": APP_VERSION,
        "disaster": DEFAULT_DISASTER,
        "mode": "DEMO (SYNTHETIC)" if has_synthetic else ("LIVE" if findings_count > 0 else "IDLE"),
        "keys_status": {
            "tinyfish_configured": is_tinyfish_configured(),
            "groq_configured": is_groq_configured(),
            "live_ready": is_live_ready()
        },
        "database": {
            "findings_count": findings_count,
            "sources_count": sources_count,
            "is_demo_loaded": has_synthetic
        }
    }


@app.get("/api/dashboard")
def get_dashboard_metrics(db: Session = Depends(get_db)):
    sources = db.query(Source).all()
    facts = db.query(ExtractedFact).all()
    findings = db.query(Finding).all()

    # Classification counts
    gap_count = sum(1 for f in findings if f.classification == "GAP")
    conflict_count = sum(1 for f in findings if f.classification == "CONFLICT")
    unknown_count = sum(1 for f in findings if f.classification == "UNKNOWN")
    covered_count = sum(1 for f in findings if f.classification == "COVERED")

    # Sources stats
    sources_discovered = len(sources)
    sources_fetched = sum(1 for s in sources if s.fetch_status == "SUCCESS")
    sources_failed = sum(1 for s in sources if s.fetch_status in ("FAILED", "BLOCKED", "EMPTY"))

    # Facts verification stats
    verified_facts_count = sum(1 for f in facts if f.is_verified)
    rejected_facts_count = sum(1 for f in facts if not f.is_verified)

    # District breakdowns
    districts_data = {}
    for d in ["Ganjam", "Gajapati"]:
        d_findings = [f for f in findings if f.district.lower() == d.lower()]
        districts_data[d] = {
            "total_findings": len(d_findings),
            "gaps": sum(1 for f in d_findings if f.classification == "GAP"),
            "conflicts": sum(1 for f in d_findings if f.classification == "CONFLICT"),
            "unknowns": sum(1 for f in d_findings if f.classification == "UNKNOWN"),
            "covered": sum(1 for f in d_findings if f.classification == "COVERED"),
            "high_priority": sum(1 for f in d_findings if f.priority == "HIGH"),
        }

    is_synthetic = any(f.is_synthetic for f in findings) or any(s.is_synthetic for s in sources)

    return {
        "event_name": DEFAULT_DISASTER,
        "is_synthetic": is_synthetic,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "sources_discovered": sources_discovered,
            "sources_fetched": sources_fetched,
            "sources_failed": sources_failed,
            "verified_facts": verified_facts_count,
            "rejected_facts": rejected_facts_count,
            "total_findings": len(findings),
            "gap_count": gap_count,
            "conflict_count": conflict_count,
            "unknown_count": unknown_count,
            "covered_count": covered_count
        },
        "districts": districts_data
    }


@app.get("/api/findings")
def list_findings(
    district: Optional[str] = Query(None),
    classification: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db)
):
    query = db.query(Finding)

    if district and district.lower() != "all":
        query = query.filter(func.lower(Finding.district) == district.lower())
    if classification and classification.lower() != "all":
        query = query.filter(func.upper(Finding.classification) == classification.upper())
    if priority and priority.lower() != "all":
        query = query.filter(func.upper(Finding.priority) == priority.upper())
    if search:
        search_filter = f"%{search.strip().lower()}%"
        query = query.filter(
            (func.lower(Finding.location).like(search_filter)) |
            (func.lower(Finding.item).like(search_filter)) |
            (func.lower(Finding.reasoning).like(search_filter))
        )

    # Sort: HIGH priority first, then GAP, CONFLICT, UNKNOWN, COVERED
    findings = query.all()

    priority_map = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    status_map = {"GAP": 0, "CONFLICT": 1, "UNKNOWN": 2, "COVERED": 3}
    findings.sort(key=lambda x: (
        priority_map.get(x.priority, 9),
        status_map.get(x.classification, 9)
    ))

    result = []
    for f in findings:
        need_fact = f.need_fact
        supply_fact = f.supply_fact
        conflict_fact = f.conflict_fact

        evidence_count = 0
        if need_fact: evidence_count += 1
        if supply_fact and supply_fact != need_fact: evidence_count += 1
        if conflict_fact and conflict_fact not in (need_fact, supply_fact): evidence_count += 1

        primary_date = (need_fact.report_date if need_fact else None) or \
                       (supply_fact.report_date if supply_fact else None) or "Recent"

        result.append({
            "id": f.id,
            "district": f.district,
            "location": f.location,
            "item": f.item,
            "classification": f.classification,
            "priority": f.priority,
            "reasoning": f.reasoning,
            "partial_percentage": f.partial_percentage,
            "report_date": primary_date,
            "evidence_count": evidence_count,
            "review_status": f.review_status,
            "reviewer_notes": f.reviewer_notes,
            "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None,
            "is_synthetic": f.is_synthetic
        })

    return {"count": len(result), "findings": result}


@app.get("/api/findings/{finding_id}")
def get_finding_detail(finding_id: int, db: Session = Depends(get_db)):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    def format_fact(fact: Optional[ExtractedFact]):
        if not fact:
            return None
        return {
            "id": fact.id,
            "location": fact.location,
            "district": fact.district,
            "item": fact.item,
            "record_type": fact.record_type,
            "quantity": fact.quantity,
            "unit": fact.unit,
            "urgency": fact.urgency,
            "report_date": fact.report_date,
            "evidence_quote": fact.evidence_quote,
            "is_verified": fact.is_verified,
            "verification_notes": fact.verification_notes,
            "source": {
                "id": fact.source.id if fact.source else None,
                "title": fact.source.title if fact.source else "External Record",
                "url": fact.source.url if fact.source else "#",
                "fetch_status": fact.source.fetch_status if fact.source else "UNKNOWN",
                "fetched_at": fact.source.fetched_at.isoformat() if fact.source and fact.source.fetched_at else None
            } if fact.source else None
        }

    reviews = [
        {
            "id": r.id,
            "action": r.action,
            "notes": r.notes,
            "created_at": r.created_at.isoformat() if r.created_at else None
        }
        for r in finding.reviews
    ]

    return {
        "id": finding.id,
        "district": finding.district,
        "location": finding.location,
        "item": finding.item,
        "classification": finding.classification,
        "priority": finding.priority,
        "reasoning": finding.reasoning,
        "partial_percentage": finding.partial_percentage,
        "review_status": finding.review_status,
        "reviewer_notes": finding.reviewer_notes,
        "reviewed_at": finding.reviewed_at.isoformat() if finding.reviewed_at else None,
        "is_synthetic": finding.is_synthetic,
        "need_fact": format_fact(finding.need_fact),
        "supply_fact": format_fact(finding.supply_fact),
        "conflict_fact": format_fact(finding.conflict_fact),
        "reviews": reviews
    }


@app.get("/api/sources")
def list_sources(db: Session = Depends(get_db)):
    sources = db.query(Source).order_by(Source.fetched_at.desc()).all()
    return {
        "count": len(sources),
        "sources": [
            {
                "id": s.id,
                "url": s.url,
                "title": s.title,
                "snippet": s.snippet,
                "text_snippet": (s.text[:300] + "...") if len(s.text) > 300 else s.text,
                "fetch_status": s.fetch_status,
                "error_msg": s.error_msg,
                "fetched_at": s.fetched_at.isoformat() if s.fetched_at else None,
                "is_synthetic": s.is_synthetic,
                "facts_count": len(s.facts)
            }
            for s in sources
        ]
    }


@app.post("/api/scan")
def trigger_scan(req: ScanRequest, db: Session = Depends(get_db)):
    pipeline = ReliefPipeline(db)

    # If user explicitly requested DEMO or if keys are not ready and mode is AUTO
    if req.mode == "DEMO" or (req.mode == "AUTO" and not is_live_ready()):
        res = pipeline.load_demo_data()
        return res

    # Otherwise LIVE MODE requested or keys available
    try:
        res = pipeline.run_live_scan(district=req.district, custom_query=req.query)
        return res
    except ValueError as ve:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Live scan error: {str(e)}")


@app.post("/api/demo/load")
def load_demo(db: Session = Depends(get_db)):
    pipeline = ReliefPipeline(db)
    res = pipeline.load_demo_data()
    return res


@app.post("/api/demo/clear")
def clear_demo(db: Session = Depends(get_db)):
    pipeline = ReliefPipeline(db)
    pipeline.clear_database()
    return {"status": "success", "message": "All data cleared successfully."}


@app.post("/api/findings/{finding_id}/review")
def review_finding(finding_id: int, req: ReviewRequest, db: Session = Depends(get_db)):
    finding = db.query(Finding).filter(Finding.id == finding_id).first()
    if not finding:
        raise HTTPException(status_code=404, detail="Finding not found")

    action = req.action.upper()
    if action not in ("APPROVE", "REJECT", "INVESTIGATE"):
        raise HTTPException(status_code=400, detail="Action must be APPROVE, REJECT, or INVESTIGATE")

    status_map = {
        "APPROVE": "APPROVED",
        "REJECT": "REJECTED",
        "INVESTIGATE": "INVESTIGATING"
    }

    finding.review_status = status_map[action]
    finding.reviewer_notes = req.notes or ""
    finding.reviewed_at = datetime.now(timezone.utc)

    # Save to history log
    action_log = ReviewAction(
        finding_id=finding.id,
        action=action,
        notes=req.notes or ""
    )
    db.add(action_log)
    db.commit()

    return {
        "status": "success",
        "finding_id": finding.id,
        "review_status": finding.review_status,
        "notes": finding.reviewer_notes,
        "reviewed_at": finding.reviewed_at.isoformat()
    }


@app.get("/api/export/csv")
def export_csv(db: Session = Depends(get_db)):
    findings = db.query(Finding).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "District", "Location", "Item", "Classification", 
        "Priority", "Partial_Percentage", "Reasoning", 
        "Review_Status", "Reviewer_Notes", "Evidence_Quote", "Source_URL", "Data_Type"
    ])

    for f in findings:
        quote = f.need_fact.evidence_quote if f.need_fact else (f.supply_fact.evidence_quote if f.supply_fact else "")
        src_url = f.need_fact.source.url if (f.need_fact and f.need_fact.source) else ""
        data_type = "SYNTHETIC_DEMO" if f.is_synthetic else "VERIFIED_LIVE"

        writer.writerow([
            f.id,
            f.district,
            f.location,
            f.item,
            f.classification,
            f.priority,
            f.partial_percentage or "",
            f.reasoning,
            f.review_status,
            f.reviewer_notes or "",
            quote,
            src_url,
            data_type
        ])

    output.seek(0)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=reliefradar_findings.csv"}
    )


@app.get("/api/export/json")
def export_json(db: Session = Depends(get_db)):
    findings = db.query(Finding).all()
    payload = []

    for f in findings:
        payload.append({
            "id": f.id,
            "district": f.district,
            "location": f.location,
            "item": f.item,
            "classification": f.classification,
            "priority": f.priority,
            "partial_percentage": f.partial_percentage,
            "reasoning": f.reasoning,
            "review_status": f.review_status,
            "reviewer_notes": f.reviewer_notes,
            "reviewed_at": f.reviewed_at.isoformat() if f.reviewed_at else None,
            "is_synthetic": f.is_synthetic,
            "need_quote": f.need_fact.evidence_quote if f.need_fact else None,
            "supply_quote": f.supply_fact.evidence_quote if f.supply_fact else None,
            "conflict_quote": f.conflict_fact.evidence_quote if f.conflict_fact else None,
            "source_url": f.need_fact.source.url if (f.need_fact and f.need_fact.source) else None
        })

    return Response(
        content=json.dumps(payload, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=reliefradar_findings.json"}
    )

# ----------------- Serve Frontend Static Files -----------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

@app.get("/")
def serve_index():
    index_file = FRONTEND_DIR / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    return {"message": "ReliefRadar API is running. Frontend index.html not found."}
