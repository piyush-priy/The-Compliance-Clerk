import re


def extract_doc_no_from_filename(filename):
    """Extract lease deed doc number from the PDF filename."""
    m = re.search(r"(?:Lease\s*Deed\s*No\.?\s*[-:]?\s*)(\d+)", filename, re.IGNORECASE)
    return m.group(1) if m else None


def extract_survey_from_filename(filename):
    """Extract survey number from a lease filename like 'S.No.- 251p2'."""
    m = re.search(r"S\.?No\.?\s*[-:]?\s*(\S+?)(?:\s+Lease|\s*$)", filename, re.IGNORECASE)
    if m:
        raw = m.group(1).strip().rstrip("-")
        # Normalize: insert / before alpha suffix (251p2 → 251/p2)
        raw = re.sub(r"(\d)([a-zA-Z])", r"\1/\2", raw)
        return raw
    return None


def extract_survey_from_na_filename(filename):
    """Extract survey number from an NA filename like '251-p2 FINAL ORDER.pdf'."""
    m = re.search(r"^([\d]+(?:[-/][a-zA-Z0-9]+)?)\s+FINAL\s+ORDER", filename, re.IGNORECASE)
    if m:
        raw = m.group(1)
        return raw.replace("-", "/")
    return None


_DATE_PATTERN = re.compile(r"\b(\d{1,2})\s*[./-]\s*(\d{1,2})\s*[./-]\s*(\d{2,4})\b")


def _normalize_whitespace(text):
	return re.sub(r"\s+", " ", text).strip()


def _normalize_for_matching(text):
	if not text:
		return ""

	# Keep Gujarati/Unicode letters but drop noisy control-like symbols.
	text = re.sub(r"[\x00-\x1f\x7f]", " ", text)
	text = text.replace("\u200c", " ").replace("\u200d", " ")

	lowered = text.lower()
	lowered = re.sub(r"sq\.?\s*m\b", "sqm", lowered)
	lowered = re.sub(r"square\s*meters?", "sqm", lowered)

	# OCR normalization in numeric contexts only.
	lowered = re.sub(r"(?<=\d)[oO](?=\d)", "0", lowered)
	lowered = re.sub(r"(?<=\d)[iIl](?=\d)", "1", lowered)
	lowered = re.sub(r"(?<=\d)[sS](?=\d)", "5", lowered)
	lowered = re.sub(r"(?<=[a-z])[0](?=[a-z])", "o", lowered)

	return _normalize_whitespace(lowered)


def _normalize_date(raw_date):
	if not raw_date:
		return None

	m = _DATE_PATTERN.search(raw_date)
	if not m:
		return None

	day = m.group(1).zfill(2)
	month = m.group(2).zfill(2)
	year = m.group(3)
	if len(year) == 2:
		year = "20" + year

	return f"{day}/{month}/{year}"


def _all_dates(text):
	dates = []
	for m in _DATE_PATTERN.finditer(text or ""):
		normalized = _normalize_date(m.group(0))
		if normalized:
			dates.append(normalized)
	return dates


def classify_page(text):
	normalized = _normalize_for_matching(text)

	if (
		"book no" in normalized
		or "registered no" in normalized
		or "registration no" in normalized
		or "document no" in normalized
		or "doc no" in normalized
		or "receipt no" in normalized
		or "serial no" in normalized
		or "sub registrar" in normalized
	):
		return "registration"

	if "lease deed" in normalized or ("lessor" in normalized and "lessee" in normalized):
		return "first_page"

	if (
		"lease term" in normalized
		or "commencing from" in normalized
		or "effective date" in normalized
		or "term of this lease" in normalized
	):
		return "term"

	if (
		"annexure" in normalized
		or "village" in normalized
		and "survey" in normalized
		and ("area" in normalized or "sqm" in normalized)
	):
		return "annexure"

	if (
		"survey no" in normalized
		or "survey number" in normalized
		or "measuring" in normalized
		or "sqm" in normalized
		or "sq.m" in normalized
	):
		return "property"

	return "other"


def _extract_doc_no(text):
	normalized = _normalize_for_matching(text)

	patterns = [
		r"book\s*no\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"registered\s*no\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"registration\s*no\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"doc(?:ument)?\s*no\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"deed\s*no\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
	]

	for pattern in patterns:
		m = re.search(pattern, normalized, flags=re.IGNORECASE)
		if m:
			token = re.sub(r"[^a-zA-Z0-9\-/]", "", m.group(1))
			return token or None

	return None


def _extract_area_candidates(text):
	normalized = _normalize_for_matching(text)
	candidates = []

	area_patterns = [
		r"(\d{1,6}(?:,\d{3})*(?:\.\d+)?)\s*(sqm|sq\.m|sq m|square\s*meters?)",
		r"(\d{1,6}(?:,\d{3})*(?:\.\d+)?)\s*(acre|acres)",
		r"(\d{1,6}(?:,\d{3})*(?:\.\d+)?)\s*(hectare|hectares|ha)\b",
	]

	for pattern in area_patterns:
		for m in re.finditer(pattern, normalized, flags=re.IGNORECASE):
			value = m.group(1).replace(",", "")
			unit = m.group(2).replace(" ", "")
			unit = "sqm" if unit in {"sq.m", "sqm", "sqmeters", "squaremeters"} else unit
			candidates.append(f"{value} {unit}")

	return candidates


def _extract_survey_number(text):
	normalized = _normalize_for_matching(text)
	patterns = [
		r"survey\s*(?:no|number)\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"block\s*(?:no|number)\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"સરવે\s*નં\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
		r"બ્લોક\s*નં\.?\s*[:\-]?\s*([a-z0-9\-/]+)",
	]

	for pattern in patterns:
		m = re.search(pattern, normalized, flags=re.IGNORECASE)
		if m:
			token = re.sub(r"[^a-zA-Z0-9\-/]", "", m.group(1))
			return token or None

	return None


def _extract_lease_start(execution_date, term_text):
	normalized = _normalize_for_matching(term_text)

	if (
		"commencing from the effective date" in normalized
		or "commencing from effective date" in normalized
	):
		return execution_date

	m = re.search(
		r"commencing\s*from\s*(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4})",
		normalized,
		flags=re.IGNORECASE,
	)
	if m:
		return _normalize_date(m.group(1))

	m = re.search(
		r"effective\s*date\s*[:\-]?\s*(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{2,4})",
		normalized,
		flags=re.IGNORECASE,
	)
	if m:
		return _normalize_date(m.group(1))

	return execution_date


def _is_plausible_execution_year(year):
	"""Filter out mutation-era dates (≤2020) and OCR-garbled future dates (>2027)."""
	return 2021 <= year <= 2027


def _extract_execution_date_consensus(classified, all_pages):
	"""Extract the lease execution date using multi-page consensus.

	Strategy:
	  1. Scan ALL raw pages (both OCR variants) for footer dates and
	     registration dates to build a candidate pool.
	  2. Filter out implausible years (mutation-era ≤2020, garbled >2027).
	  3. Registration-page dates (`on Date DD/MM/YYYY`, `Date: DD-MM-YYYY`
	     on page 51) get highest priority — they are printed large and
	     OCR cleanly.
	  4. Among remaining candidates, vote by (day, month, year) frequency.
	     The most-frequent date wins.
	"""
	from collections import Counter

	# Pool: list of (date_str, source_priority)
	#   source_priority: 0 = registration-page, 1 = footer Date:, 2 = any date
	candidates = []

	# Gather raw text from ALL available pages (before footer stripping)
	raw_pages = list(all_pages or []) + [p for p in classified]

	for page in raw_pages:
		text = page.get("text") or ""
		page_num = page.get("page")

		# --- Registration-page patterns (highest priority) ---
		# Pattern: "on Date\n28/05/2025" or "Date:\n28/05/2025"
		for m in re.finditer(
			r"(?:on\s+Date|Date\s*[:\-])\s*\n?\s*(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})",
			text, flags=re.IGNORECASE
		):
			nd = _normalize_date(m.group(1))
			if nd:
				year = int(nd.split("/")[-1])
				if _is_plausible_execution_year(year):
					candidates.append((nd, 0))

		# Pattern: "Serial No. NNN ... Date\nDD/MM/YYYY" on registration page
		for m in re.finditer(
			r"Serial\s*No\.?\s*\d+.*?(?:on\s+Date|Date)\s*\n?\s*(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})",
			text, flags=re.IGNORECASE | re.DOTALL
		):
			nd = _normalize_date(m.group(1))
			if nd:
				year = int(nd.split("/")[-1])
				if _is_plausible_execution_year(year):
					candidates.append((nd, 0))

		# Pattern: "(G2.0) DD/MM/YYYY HH:MM" — Garvi registration header
		for m in re.finditer(
			r"\(G2\.0\)\s*(\d{1,2}/\d{1,2}/\d{4})",
			text
		):
			nd = _normalize_date(m.group(1))
			if nd:
				year = int(nd.split("/")[-1])
				if _is_plausible_execution_year(year):
					candidates.append((nd, 0))

		# --- Footer "Date: DD-MM-YYYY" from page footers (medium priority) ---
		for m in re.finditer(
			r"Date\s*[:\-]\s*(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})",
			text, flags=re.IGNORECASE
		):
			nd = _normalize_date(m.group(1))
			if nd:
				year = int(nd.split("/")[-1])
				if _is_plausible_execution_year(year):
					candidates.append((nd, 1))

		# --- Page footer pattern: "Page X of Y, Date: DD-MM-YYYY" ---
		for m in re.finditer(
			r"Page\s*\d+\s*(?:of|०[fF])\s*\d+\s*,?\s*Date\s*[:\-]\s*(\d{1,2}\s*[./-]\s*\d{1,2}\s*[./-]\s*\d{4})",
			text, flags=re.IGNORECASE
		):
			nd = _normalize_date(m.group(1))
			if nd:
				year = int(nd.split("/")[-1])
				if _is_plausible_execution_year(year):
					candidates.append((nd, 1))

	if not candidates:
		# Absolute last resort: any recent date from any page
		for page in raw_pages:
			dates = _all_dates(page.get("text") or "")
			for d in dates:
				year = int(d.split("/")[-1])
				if _is_plausible_execution_year(year):
					candidates.append((d, 2))

	if not candidates:
		return None

	# Sort by priority first, then by frequency among same-priority candidates
	best_priority = min(c[1] for c in candidates)
	top_candidates = [c[0] for c in candidates if c[1] == best_priority]

	# Vote by frequency: most common date wins
	counter = Counter(top_candidates)
	winner, _count = counter.most_common(1)[0]
	return winner


def extract_lease_record_from_pages(pages, all_pages=None):
	classified = []
	for p in pages:
		text = p.get("text") or ""
		classified.append(
			{
				"page": p.get("page"),
				"text": text,
				"page_type": classify_page(text),
			}
		)

	page_groups = {
		"registration": [],
		"first_page": [],
		"property": [],
		"term": [],
		"annexure": [],
		"other": [],
	}
	for item in classified:
		page_groups[item["page_type"]].append(item)

	doc_no = None
	for page in page_groups["registration"] + page_groups["first_page"]:
		doc_no = _extract_doc_no(page["text"])
		if doc_no:
			break

	annexure_areas = []
	for page in page_groups["annexure"]:
		annexure_areas.extend(_extract_area_candidates(page["text"]))

	property_areas = []
	for page in page_groups["property"]:
		property_areas.extend(_extract_area_candidates(page["text"]))

	any_areas = []
	for page in classified:
		any_areas.extend(_extract_area_candidates(page["text"]))

	lease_area = (annexure_areas or property_areas or any_areas or [None])[0]

	# Multi-page date consensus: scan all pages + OCR variants for the
	# most consistent execution date, filtering mutation-era and OCR-garbled years.
	execution_date = _extract_execution_date_consensus(classified, all_pages)

	term_blob = "\n".join(page["text"] for page in page_groups["term"])
	lease_start = _extract_lease_start(execution_date, term_blob)

	survey_number = None
	for page in page_groups["annexure"] + page_groups["property"] + page_groups["first_page"]:
		survey_number = _extract_survey_number(page["text"])
		if survey_number:
			break

	return {
		"survey_number": survey_number,
		"lease_deed_doc_no": doc_no,
		"lease_area": lease_area,
		"lease_start": lease_start,
		# Legacy compatibility aliases for existing normalization layer.
		"land_area": lease_area,
		"lease_start_date": lease_start,
		"_lease_page_types": [{"page": p["page"], "type": p["page_type"]} for p in classified],
	}
