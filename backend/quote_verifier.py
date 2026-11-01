import re
import unicodedata

def normalize_text(text: str) -> str:
    """
    Normalizes whitespace and unicode characters safely for robust substring matching
    without altering substantive content.
    """
    if not text:
        return ""
    # Normalize unicode (NFKC)
    text = unicodedata.normalize("NFKC", text)
    # Replace curly quotes and apostrophes with standard ASCII
    text = text.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    # Collapse all whitespace sequences (spaces, tabs, newlines) into a single space
    text = re.sub(r"\s+", " ", text).strip()
    return text

def verify_quote(source_text: str, evidence_quote: str) -> tuple[bool, str]:
    """
    Verifies that the evidence quote is an exact, non-hallucinated substring 
    of the source document text.

    Returns:
        (is_verified: bool, message: str)
    """
    if not evidence_quote or not evidence_quote.strip():
        return False, "Rejected: Evidence quote is empty."

    if not source_text or not source_text.strip():
        return False, "Rejected: Source text is empty or unavailable."

    raw_quote = evidence_quote.strip()
    # Strip enclosing quotes if model wrapped the string in quotes
    if (raw_quote.startswith('"') and raw_quote.endswith('"')) or (raw_quote.startswith("'") and raw_quote.endswith("'")):
        if len(raw_quote) > 2:
            raw_quote = raw_quote[1:-1].strip()

    if len(raw_quote) < 5:
        return False, "Rejected: Evidence quote is too brief to substantiate claim."

    # First check: exact raw match
    if raw_quote in source_text:
        return True, "Verified: Exact literal substring matched in source text."

    # Second check: normalized whitespace match
    norm_source = normalize_text(source_text)
    norm_quote = normalize_text(raw_quote)

    if norm_quote in norm_source:
        return True, "Verified: Exact normalized substring matched in source text."

    # Check case-insensitive normalized match if close
    if norm_quote.lower() in norm_source.lower():
        return True, "Verified: Substring matched in source text (case-adjusted)."

    return False, "Rejected: Fabricated quotation. Quote does not exist in the source text."
