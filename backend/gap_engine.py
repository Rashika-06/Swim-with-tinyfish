from typing import List, Dict, Any, Optional
from datetime import datetime

# Priority ordering
PRIORITY_HIGH = "HIGH"
PRIORITY_MEDIUM = "MEDIUM"
PRIORITY_LOW = "LOW"

# Status constants
STATUS_GAP = "GAP"
STATUS_CONFLICT = "CONFLICT"
STATUS_UNKNOWN = "UNKNOWN"
STATUS_COVERED = "COVERED"

CRITICAL_ITEMS = {"drinking water", "water", "medical", "medicines", "rescue", "food", "food rations"}

def classify_location_item(
    location: str,
    district: str,
    item: str,
    facts: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    """
    Deterministic rule-based classification engine for a single location and item.
    Only verified facts are evaluated.
    
    Returns finding dictionary with:
      - classification: GAP | CONFLICT | UNKNOWN | COVERED
      - priority: HIGH | MEDIUM | LOW
      - reasoning: Detailed humanitarian rationale
      - need_fact_id: ID of primary need fact
      - supply_fact_id: ID of primary supply fact (if any)
      - conflict_fact_id: ID of conflicting fact (if any)
      - partial_percentage: Float percentage if partial fulfillment
    """
    # Filter to verified facts for this location and item (case-insensitive)
    loc_facts = [
        f for f in facts
        if f.get("is_verified", False)
        and f.get("location", "").strip().lower() == location.strip().lower()
        and f.get("item", "").strip().lower() == item.strip().lower()
    ]

    if not loc_facts:
        return None

    needs = [f for f in loc_facts if f.get("record_type") == "NEED"]
    supplies = [f for f in loc_facts if f.get("record_type") in ("SUPPLY", "RESTORATION")]
    
    # If no need was reported, but supplies were reported, check if it's preventative/covered
    if not needs and supplies:
        primary_supply = supplies[0]
        return {
            "district": district,
            "location": location,
            "item": item,
            "classification": STATUS_COVERED,
            "priority": PRIORITY_LOW,
            "reasoning": f"Supply reported without unmet need request: {primary_supply.get('evidence_quote', '')}",
            "need_fact_id": None,
            "supply_fact_id": primary_supply.get("id"),
            "conflict_fact_id": None,
            "partial_percentage": 100.0
        }

    if not needs:
        return None

    primary_need = needs[0]
    need_qty = primary_need.get("quantity")
    need_quote = primary_need.get("evidence_quote", "")
    urgency = (primary_need.get("urgency") or "UNKNOWN").upper()

    # 1. CHECK CONFLICT FIRST
    # Contradiction: e.g. An official restoration claim vs an active unmet ground dispatch,
    # or two contradictory supply/situation claims.
    for supply in supplies:
        supply_quote = supply.get("evidence_quote", "").lower()
        need_quote_lower = need_quote.lower()

        # Evidence contradictory signals
        restored_signals = ["restored", "100%", "fully operational", "normalcy", "no shortage", "completed"]
        unmet_signals = ["no ", "zero", "lacking", "stranded", "failed", "cut off", "severe crisis", "contamination", "shortage"]

        is_supply_positive = any(s in supply_quote for s in restored_signals) or supply.get("record_type") == "RESTORATION"
        is_need_unmet = any(s in need_quote_lower for s in unmet_signals) or urgency in ("CRITICAL", "HIGH")

        # Explicit contradiction check
        if is_supply_positive and is_need_unmet:
            return {
                "district": district,
                "location": location,
                "item": item,
                "classification": STATUS_CONFLICT,
                "priority": PRIORITY_HIGH,
                "reasoning": (
                    f"Direct contradiction detected: Official claim reports restoration/availability "
                    f"('{supply.get('evidence_quote')}'), whereas field reports report acute unmet need "
                    f"('{primary_need.get('evidence_quote')}'). Requires urgent coordinator verification."
                ),
                "need_fact_id": primary_need.get("id"),
                "supply_fact_id": supply.get("id"),
                "conflict_fact_id": supply.get("id"),
                "partial_percentage": None
            }

    # 2. CHECK EXPLICIT GAP
    # A GAP requires evidence explicitly establishing an unmet supply shortfall.
    # We do NOT classify mere missing information as a gap.
    is_explicit_unmet = False
    shortfall_reason = ""
    partial_pct = None

    # Check text evidence for explicit zero supply or shortfall (using word boundaries to avoid false positives on numbers like '4,000')
    import re
    zero_patterns = [
        r"\bzero\b",
        r"\b0\s*(tankers|supplies|packets|kits|delivered|reached|units|percent|%)\b",
        r"\bnone\s+received\b",
        r"\bno\s+(supply|tankers|aid|relief|delivery)\b",
        r"\bno\s+clean\s+(drinking\s+)?water\b",
        r"\bno\s+aid\s+reached\b",
        r"\bnot\s+a\s+single\b",
        r"\bunmet\s+shortfall\b",
        r"\bzero\s+water\s+tankers\b"
    ]
    if any(re.search(pat, need_quote, re.IGNORECASE) for pat in zero_patterns):
        is_explicit_unmet = True
        shortfall_reason = f"Field evidence explicitly documents zero supply delivery: '{need_quote}'"

    # Compare numeric quantities if both exist
    if supplies:
        primary_supply = supplies[0]
        supply_qty = primary_supply.get("quantity")

        if supply_qty is not None and need_qty is not None and need_qty > 0:
            if supply_qty == 0:
                is_explicit_unmet = True
                shortfall_reason = f"Need of {need_qty} {primary_need.get('unit') or 'units'} reported, with verified 0 supply delivered."
            elif supply_qty < need_qty:
                partial_pct = round((supply_qty / need_qty) * 100, 1)
                is_explicit_unmet = True
                shortfall_reason = (
                    f"Partial shortfall: Only {supply_qty} of requested {need_qty} "
                    f"{primary_need.get('unit') or 'units'} delivered ({partial_pct}% fulfilled)."
                )
            elif supply_qty >= need_qty:
                # 3. COVERED
                return {
                    "district": district,
                    "location": location,
                    "item": item,
                    "classification": STATUS_COVERED,
                    "priority": PRIORITY_LOW,
                    "reasoning": (
                        f"Need verified as covered: {supply_qty} {primary_supply.get('unit') or 'units'} "
                        f"delivered, meeting or exceeding requirement of {need_qty}."
                    ),
                    "need_fact_id": primary_need.get("id"),
                    "supply_fact_id": primary_supply.get("id"),
                    "conflict_fact_id": None,
                    "partial_percentage": 100.0
                }
        elif supply_qty is not None and supply_qty > 0 and need_qty is None:
            # Positive supply delivered without quantified target
            return {
                "district": district,
                "location": location,
                "item": item,
                "classification": STATUS_COVERED,
                "priority": PRIORITY_LOW,
                "reasoning": f"Verified supply of {supply_qty} {primary_supply.get('unit') or ''} delivered to location.",
                "need_fact_id": primary_need.get("id"),
                "supply_fact_id": primary_supply.get("id"),
                "conflict_fact_id": None,
                "partial_percentage": 100.0
            }

    if is_explicit_unmet:
        # Determine priority based on urgency and item criticality
        is_critical = item.lower() in CRITICAL_ITEMS or urgency in ("CRITICAL", "HIGH")
        priority = PRIORITY_HIGH if is_critical else PRIORITY_MEDIUM

        return {
            "district": district,
            "location": location,
            "item": item,
            "classification": STATUS_GAP,
            "priority": priority,
            "reasoning": shortfall_reason,
            "need_fact_id": primary_need.get("id"),
            "supply_fact_id": supplies[0].get("id") if supplies else None,
            "conflict_fact_id": None,
            "partial_percentage": partial_pct
        }

    # 4. UNKNOWN
    # A need is reported, but supply fulfillment cannot be established / is unpublished.
    # Missing supply information is explicitly classified as UNKNOWN (Never guessed, Never GAP).
    return {
        "district": district,
        "location": location,
        "item": item,
        "classification": STATUS_UNKNOWN,
        "priority": PRIORITY_HIGH if item.lower() in CRITICAL_ITEMS else PRIORITY_MEDIUM,
        "reasoning": (
            f"Need reported ({primary_need.get('quantity') or 'Unspecified'} "
            f"{primary_need.get('unit') or 'units'}), but supply fulfilment data is "
            f"'Not published'. ReliefRadar refuses to guess missing quantities."
        ),
        "need_fact_id": primary_need.get("id"),
        "supply_fact_id": None,
        "conflict_fact_id": None,
        "partial_percentage": None
    }


def evaluate_all_facts(facts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Evaluates all unique location-item pairs across verified extracted facts.
    """
    # Group unique (district, location, item) tuples
    pairs = set()
    for f in facts:
        if f.get("is_verified", False):
            district = f.get("district", "").strip()
            location = f.get("location", "").strip()
            item = f.get("item", "").strip()
            if district and location and item:
                pairs.add((district, location, item))

    findings = []
    for district, location, item in sorted(pairs):
        finding = classify_location_item(location, district, item, facts)
        if finding:
            findings.append(finding)

    # Sort findings by Priority (HIGH -> MEDIUM -> LOW) and Status (GAP, CONFLICT, UNKNOWN, COVERED)
    priority_order = {PRIORITY_HIGH: 0, PRIORITY_MEDIUM: 1, PRIORITY_LOW: 2}
    status_order = {STATUS_GAP: 0, STATUS_CONFLICT: 1, STATUS_UNKNOWN: 2, STATUS_COVERED: 3}

    findings.sort(
        key=lambda x: (
            priority_order.get(x["priority"], 9),
            status_order.get(x["classification"], 9),
            x["district"],
            x["location"]
        )
    )
    return findings
