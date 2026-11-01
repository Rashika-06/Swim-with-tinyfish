import pytest
from backend.quote_verifier import verify_quote, normalize_text

def test_exact_quote_match():
    source_text = "NDRF delivered 1,600 waterproof tarpaulin kits to Gopalpur Cyclone Shelter #4."
    quote = "NDRF delivered 1,600 waterproof tarpaulin kits"
    is_valid, msg = verify_quote(source_text, quote)
    assert is_valid is True
    assert "Verified" in msg

def test_whitespace_and_newline_normalization():
    source_text = "Villagers in   Mohana block\nreport zero water tankers\treached."
    quote = "Villagers in Mohana block report zero water tankers reached."
    is_valid, msg = verify_quote(source_text, quote)
    assert is_valid is True
    assert "Verified" in msg

def test_curly_quotes_normalization():
    source_text = 'District announced “water supply fully restored” in coastal colonies.'
    quote = 'District announced "water supply fully restored" in coastal colonies.'
    is_valid, msg = verify_quote(source_text, quote)
    assert is_valid is True
    assert "Verified" in msg

def test_fabricated_quote_rejected():
    source_text = "Minor water logging reported near national highway 16."
    fabricated = "Entire town submerged under 10 feet of water with 500 casualties."
    is_valid, msg = verify_quote(source_text, fabricated)
    assert is_valid is False
    assert "Rejected" in msg

def test_empty_quote_rejected():
    source_text = "Relief camps operational in Ganjam."
    is_valid, msg = verify_quote(source_text, "")
    assert is_valid is False
    assert "Rejected" in msg

def test_empty_source_rejected():
    is_valid, msg = verify_quote("", "Valid quotation text")
    assert is_valid is False
    assert "Rejected" in msg

def test_quote_too_short_rejected():
    source_text = "Relief camps operational in Ganjam."
    is_valid, msg = verify_quote(source_text, "cam")
    assert is_valid is False
    assert "Rejected" in msg
