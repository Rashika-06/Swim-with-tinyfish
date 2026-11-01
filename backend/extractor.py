import json
import logging
from typing import List, Dict, Any, Optional

from backend.config import GROQ_API_KEY, is_groq_configured

logger = logging.getLogger(__name__)

ALLOWED_RECORD_TYPES = {"NEED", "SUPPLY", "DAMAGE", "RESTORATION", "RESCUE"}

SYSTEM_PROMPT = """You are an expert humanitarian relief intelligence analyst.
Your task is to extract factual relief claims from disaster situation reports into structured JSON.

CRITICAL EXTRACTION RULES:
1. Extract ONLY facts explicitly stated in the source text.
2. NEVER invent or guess quantities, dates, or items.
3. Every fact MUST contain an EXACT verbatim quotation (`evidence_quote`) from the source text that substantiates the claim.
4. Allowed `record_type` values are strictly: "NEED", "SUPPLY", "DAMAGE", "RESTORATION", "RESCUE".
5. Distinguish requested needs from dispatched or delivered supplies.
6. Urgency can be: "CRITICAL", "HIGH", "MEDIUM", "LOW", "UNKNOWN".
7. Return an empty array `{"facts": []}` if no disaster relief facts are present in the text.
8. DO NOT assign final classifications (GAP/CONFLICT/UNKNOWN/COVERED). Return only the raw structured evidence.

OUTPUT FORMAT:
Return valid JSON with the following schema:
{
  "facts": [
    {
      "location": "Specific town/block/ward",
      "district": "Ganjam or Gajapati or specified district",
      "item": "e.g. Drinking Water, Food Rations, Tarpaulins, Emergency Medical Power",
      "record_type": "NEED",
      "quantity": 500,
      "unit": "families / packets / kits / tablets / percent",
      "urgency": "CRITICAL",
      "report_date": "YYYY-MM-DD or date string",
      "evidence_quote": "Exact verbatim quote from the text supporting this finding"
    }
  ]
}
"""

class ReliefExtractor:
    """
    Handles structured evidence extraction using Groq LLM API.
    In LIVE MODE: Calls Groq API using GROQ_API_KEY.
    Validates model output schema before returning.
    """
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or GROQ_API_KEY

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    def extract_facts_from_text(
        self,
        source_text: str,
        source_url: str,
        source_title: str,
        district_hint: str = "Odisha"
    ) -> List[Dict[str, Any]]:
        """
        Calls Groq API to extract structured facts from source text.
        Raises ValueError or RuntimeError if API is unconfigured or fails.
        """
        if not self.is_configured():
            raise ValueError(
                "Groq API key is not configured. "
                "Please set GROQ_API_KEY in your local .env file to run in LIVE MODE."
            )

        if not source_text or len(source_text.strip()) < 50:
            return []

        from groq import Groq

        # Prefer requested model, with fallback if model is unavailable
        models_to_try = ["openai/gpt-oss-20b", "llama-3.3-70b-versatile", "llama-3.1-8b-instant"]

        client = Groq(api_key=self.api_key)
        
        user_prompt = f"""Source Title: {source_title}
Source URL: {source_url}
Target District/Region: {district_hint}

Source Document Text:
\"\"\"
{source_text[:12000]}
\"\"\"

Extract all verifiable disaster relief facts according to the system instructions.
"""

        raw_response_text = ""
        last_error = None

        for model_name in models_to_try:
            try:
                logger.info(f"Attempting Groq extraction with model '{model_name}'")
                completion = client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": user_prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.1,
                    max_tokens=2048
                )
                raw_response_text = completion.choices[0].message.content
                break
            except Exception as e:
                logger.warning(f"Groq model '{model_name}' error: {e}")
                last_error = e

        if not raw_response_text:
            raise RuntimeError(f"Groq API call failed across attempted models: {last_error}")

        # Parse and strictly validate JSON
        try:
            parsed = json.loads(raw_response_text)
            raw_facts = parsed.get("facts", [])
            if not isinstance(raw_facts, list):
                raw_facts = []

            validated_facts = []
            for item in raw_facts:
                if not isinstance(item, dict):
                    continue

                location = str(item.get("location") or "").strip()
                district = str(item.get("district") or district_hint or "Odisha").strip()
                relief_item = str(item.get("item") or "").strip()
                record_type = str(item.get("record_type") or "NEED").strip().upper()
                evidence_quote = str(item.get("evidence_quote") or "").strip()

                if not location or not relief_item or not evidence_quote:
                    continue

                if record_type not in ALLOWED_RECORD_TYPES:
                    record_type = "NEED"

                qty = item.get("quantity")
                try:
                    qty = float(qty) if qty is not None else None
                except (ValueError, TypeError):
                    qty = None

                validated_facts.append({
                    "location": location,
                    "district": district,
                    "item": relief_item,
                    "record_type": record_type,
                    "quantity": qty,
                    "unit": str(item.get("unit") or "").strip() or None,
                    "urgency": str(item.get("urgency") or "UNKNOWN").strip().upper(),
                    "report_date": str(item.get("report_date") or "").strip() or None,
                    "source_url": source_url,
                    "source_title": source_title,
                    "evidence_quote": evidence_quote
                })

            return validated_facts

        except json.JSONDecodeError as err:
            logger.error(f"Failed to parse Groq JSON response: {err}")
            raise ValueError(f"Groq produced invalid JSON output: {err}")
