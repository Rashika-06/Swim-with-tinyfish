import pytest
from backend.gap_engine import (
    classify_location_item,
    evaluate_all_facts,
    STATUS_GAP,
    STATUS_CONFLICT,
    STATUS_UNKNOWN,
    STATUS_COVERED,
    PRIORITY_HIGH
)

def test_explicit_gap_zero_supply():
    facts = [
        {
            "id": 1,
            "district": "Gajapati",
            "location": "Mohana",
            "item": "Drinking Water",
            "record_type": "NEED",
            "quantity": 500,
            "unit": "families",
            "urgency": "CRITICAL",
            "evidence_quote": "Villagers in Mohana report zero water tankers reached and no drinking water for 72 hours.",
            "is_verified": True
        }
    ]
    res = classify_location_item("Mohana", "Gajapati", "Drinking Water", facts)
    assert res is not None
    assert res["classification"] == STATUS_GAP
    assert res["priority"] == PRIORITY_HIGH
    assert "zero" in res["reasoning"].lower() or "shortfall" in res["reasoning"].lower()

def test_missing_supply_is_unknown_not_gap():
    """
    CRITICAL RULE: A reported need where supply info is missing/not published
    must NOT be classified as GAP; it must be UNKNOWN.
    """
    facts = [
        {
            "id": 2,
            "district": "Ganjam",
            "location": "Chhatrapur",
            "item": "Dry Food Rations",
            "record_type": "NEED",
            "quantity": 4000,
            "unit": "packets",
            "urgency": "HIGH",
            "evidence_quote": "Over 4,000 packets of dry food rations requested for stranded low-lying wards in Chhatrapur.",
            "is_verified": True
        }
    ]
    res = classify_location_item("Chhatrapur", "Ganjam", "Dry Food Rations", facts)
    assert res is not None
    assert res["classification"] == STATUS_UNKNOWN
    assert res["classification"] != STATUS_GAP
    assert "Not published" in res["reasoning"]

def test_conflict_detection():
    facts = [
        {
            "id": 3,
            "district": "Ganjam",
            "location": "Berhampur MKCG Hospital",
            "item": "Emergency Medical Power",
            "record_type": "RESTORATION",
            "quantity": 100,
            "unit": "percent",
            "urgency": "LOW",
            "evidence_quote": "District Administration confirmed backup diesel generators at Berhampur MKCG Medical College are 100% restored.",
            "is_verified": True
        },
        {
            "id": 4,
            "district": "Ganjam",
            "location": "Berhampur MKCG Hospital",
            "item": "Emergency Medical Power",
            "record_type": "NEED",
            "quantity": 1,
            "unit": "ICU Unit",
            "urgency": "CRITICAL",
            "evidence_quote": "Field volunteer doctors report ICU backup generator failed, critical oxygen shortage with severe crisis in neonatal ward.",
            "is_verified": True
        }
    ]
    res = classify_location_item("Berhampur MKCG Hospital", "Ganjam", "Emergency Medical Power", facts)
    assert res is not None
    assert res["classification"] == STATUS_CONFLICT
    assert res["priority"] == PRIORITY_HIGH
    assert res["conflict_fact_id"] is not None

def test_covered_classification():
    facts = [
        {
            "id": 5,
            "district": "Ganjam",
            "location": "Gopalpur",
            "item": "Tarpaulins",
            "record_type": "NEED",
            "quantity": 1500,
            "unit": "kits",
            "urgency": "MEDIUM",
            "evidence_quote": "Need 1,500 tarpaulin kits for damaged coastal huts.",
            "is_verified": True
        },
        {
            "id": 6,
            "district": "Ganjam",
            "location": "Gopalpur",
            "item": "Tarpaulins",
            "record_type": "SUPPLY",
            "quantity": 1600,
            "unit": "kits",
            "urgency": "LOW",
            "evidence_quote": "Delivered 1,600 waterproof tarpaulin kits to Gopalpur Cyclone Shelter #4.",
            "is_verified": True
        }
    ]
    res = classify_location_item("Gopalpur", "Ganjam", "Tarpaulins", facts)
    assert res is not None
    assert res["classification"] == STATUS_COVERED
    assert res["partial_percentage"] == 100.0

def test_partial_fulfillment():
    facts = [
        {
            "id": 7,
            "district": "Ganjam",
            "location": "Hinjilicut",
            "item": "Water Purification Tablets",
            "record_type": "NEED",
            "quantity": 10000,
            "unit": "tablets",
            "urgency": "HIGH",
            "evidence_quote": "Health center reports urgent requirement of 10,000 water purification halogen tablets.",
            "is_verified": True
        },
        {
            "id": 8,
            "district": "Ganjam",
            "location": "Hinjilicut",
            "item": "Water Purification Tablets",
            "record_type": "SUPPLY",
            "quantity": 3000,
            "unit": "tablets",
            "urgency": "MEDIUM",
            "evidence_quote": "Block office dispatched 3,000 water purification tablets to Hinjilicut primary health center.",
            "is_verified": True
        }
    ]
    res = classify_location_item("Hinjilicut", "Ganjam", "Water Purification Tablets", facts)
    assert res is not None
    assert res["classification"] == STATUS_GAP
    assert res["partial_percentage"] == 30.0
    assert "Partial shortfall: Only 3000" in res["reasoning"]

def test_unverified_facts_ignored():
    facts = [
        {
            "id": 9,
            "district": "Gajapati",
            "location": "Paralakhemundi",
            "item": "Drone Aid Delivery",
            "record_type": "SUPPLY",
            "quantity": 50000,
            "unit": "kits",
            "urgency": "LOW",
            "evidence_quote": "Fabricated quote that failed verification",
            "is_verified": False  # REJECTED BY QUOTE VERIFIER
        }
    ]
    res = classify_location_item("Paralakhemundi", "Gajapati", "Drone Aid Delivery", facts)
    assert res is None  # Unverified facts must not generate findings
