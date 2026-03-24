"""Deterministic (regex-based) extraction for NA order documents.

NA orders follow a rigid Gujarati template on page 1.  Extracting with
regex is both faster and more reliable than sending the text to an LLM,
and avoids token-budget / rate-limit constraints entirely.
"""

import re

# ── Gujarati-digit → ASCII-digit table ──────────────────────────────
_GUJ_DIGITS = str.maketrans("૦૧૨૩૪૫૬૭૮૯", "0123456789")


def _guj_to_ascii(text):
    """Convert Gujarati numerals to ASCII digits."""
    return text.translate(_GUJ_DIGITS)


def _clean_number(raw):
    """Strip commas, units, whitespace and return a plain integer string."""
    if not raw:
        return None
    cleaned = re.sub(r"[^\d.]", "", raw)
    if not cleaned:
        return None
    try:
        num = float(cleaned)
        return str(int(num)) if num == int(num) else cleaned
    except (ValueError, OverflowError):
        return cleaned


# ── Gujarati village-name transliteration (common names) ────────────
_VILLAGE_MAP = {
    "રામપુરા મોટા": "Rampura Mota",
    "રામપુરા": "Rampura",
}


def _transliterate_village(gujarati_name):
    if not gujarati_name:
        return None
    gujarati_name = gujarati_name.strip()
    # Try exact match first, then prefix match
    if gujarati_name in _VILLAGE_MAP:
        return _VILLAGE_MAP[gujarati_name]
    for guj, eng in _VILLAGE_MAP.items():
        if guj in gujarati_name:
            return eng
    # Fallback: return as-is
    return gujarati_name


def extract_na_record_from_text(text):
    """Extract all NA order fields from page-1 text using regex.

    Returns a dict with keys matching the merge expectations:
      survey_number, village, na_area, order_date, na_order_no
    """
    if not text:
        return {}

    ascii_text = _guj_to_ascii(text)

    # ── Order number: હુકમ નં. XXXX ──
    na_order_no = None
    m = re.search(
        r"હુકમ\s*નં\.?\s*[:\-]?\s*([A-Za-z0-9/\-]+)",
        ascii_text,
    )
    if m:
        na_order_no = m.group(1).strip()

    # ── Order date: તા.DD/MM/YYYY ──
    # The order date appears right after the district line (જિ. ...).
    # The preamble also has dates (from older circulars) so we can't just
    # pick the first match.  Instead, anchor after the district header.
    order_date = None
    m = re.search(
        r"જિ\.\s*[^\n]+\nતા\.?\s*(\d{1,2}/\d{1,2}/\d{4})",
        ascii_text,
    )
    if m:
        order_date = m.group(1)
    else:
        # Fallback: last તા. with ASCII digits before the હુકમ section
        date_matches = re.findall(r"તા\.?\s*(\d{1,2}/\d{1,2}/\d{4})", ascii_text)
        if len(date_matches) >= 2:
            order_date = date_matches[1]  # second match (after preamble)
        elif date_matches:
            order_date = date_matches[0]

    # ── Village: ગામ XXXXX સરવે ──
    village = None
    m = re.search(r"ગામ\s+(.+?)\s+સરવે", ascii_text)
    if m:
        village = _transliterate_village(m.group(1).strip())

    # ── Survey number: સરવે/બ્લોક નંબર XXX ──
    survey_number = None
    m = re.search(
        r"સરવે/બ્લોક\s*નંબર\s+([A-Za-z0-9/\-]+)",
        ascii_text,
    )
    if m:
        survey_number = m.group(1).strip()

    # ── Total area (વિસ્તાર): the number right after વિસ્તાર ──
    # Pattern: "વિસ્તાર 16,534.00 ચો.મી."
    # NOT the ક્ષેત્રફળ (leased subset) that comes after પૈકી
    na_area = None
    m = re.search(
        r"વિસ્તાર\s+([\d,]+(?:\.\d+)?)\s*ચો\.?\s*મી",
        ascii_text,
    )
    if m:
        na_area = _clean_number(m.group(1))

    return {
        "survey_number": survey_number,
        "village": village,
        "na_area": na_area,
        "order_date": order_date,
        "na_order_no": na_order_no,
    }
