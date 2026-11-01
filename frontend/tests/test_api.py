import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.database import Base, engine

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield

def test_health_endpoint():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "keys_status" in data
    assert "database" in data

def test_load_demo_data():
    response = client.post("/api/demo/load")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["sources_loaded"] >= 4
    assert data["facts_extracted"] >= 6
    assert data["verified_quotes"] > 0
    # There is 1 intentional fabricated quote in mock_data.json
    assert data["rejected_quotes"] >= 1
    assert data["findings_generated"] >= 4

def test_dashboard_metrics():
    # Demo data is loaded
    response = client.get("/api/dashboard")
    assert response.status_code == 200
    data = response.json()
    summary = data["summary"]
    assert summary["gap_count"] >= 1
    assert summary["conflict_count"] >= 1
    assert summary["unknown_count"] >= 1
    assert summary["covered_count"] >= 1
    assert data["is_synthetic"] is True
    assert "Ganjam" in data["districts"]
    assert "Gajapati" in data["districts"]

def test_list_findings_and_filters():
    # Filter by classification=GAP
    res_gap = client.get("/api/findings?classification=GAP")
    assert res_gap.status_code == 200
    gap_data = res_gap.json()
    assert gap_data["count"] >= 1
    for f in gap_data["findings"]:
        assert f["classification"] == "GAP"

    # Filter by district=Gajapati
    res_dist = client.get("/api/findings?district=Gajapati")
    assert res_dist.status_code == 200
    dist_data = res_dist.json()
    assert dist_data["count"] >= 1
    for f in dist_data["findings"]:
        assert f["district"] == "Gajapati"

def test_finding_detail():
    findings_res = client.get("/api/findings")
    findings = findings_res.json()["findings"]
    assert len(findings) > 0
    f_id = findings[0]["id"]

    detail_res = client.get(f"/api/findings/{f_id}")
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["id"] == f_id
    assert "reasoning" in detail
    assert "need_fact" in detail

def test_coordinator_review_action():
    findings_res = client.get("/api/findings")
    f_id = findings_res.json()["findings"][0]["id"]

    review_payload = {
        "action": "APPROVE",
        "notes": "Verified with district control room. Water tankers dispatched."
    }
    review_res = client.post(f"/api/findings/{f_id}/review", json=review_payload)
    assert review_res.status_code == 200
    res_data = review_res.json()
    assert res_data["review_status"] == "APPROVED"
    assert res_data["notes"] == review_payload["notes"]

    # Check updated finding
    detail_res = client.get(f"/api/findings/{f_id}")
    assert detail_res.json()["review_status"] == "APPROVED"
    assert len(detail_res.json()["reviews"]) >= 1

def test_export_csv():
    res = client.get("/api/export/csv")
    assert res.status_code == 200
    assert "text/csv" in res.headers["content-type"]
    assert "District,Location,Item" in res.text

def test_export_json():
    res = client.get("/api/export/json")
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    data = res.json()
    assert isinstance(data, list)
    assert len(data) > 0

def test_live_scan_without_keys_fails_explicitly():
    # LIVE mode must fail with a clear configuration message if keys are not present
    payload = {"district": "Ganjam", "mode": "LIVE"}
    res = client.post("/api/scan", json=payload)
    # If keys are not set, it should return 400 Bad Request with a clear message
    assert res.status_code in (400, 502)
    assert "TINYFISH_API_KEY" in res.text or "API key" in res.text
