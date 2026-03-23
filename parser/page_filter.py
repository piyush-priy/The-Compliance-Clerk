def _contains_alnum(line):
    return any(c.isalnum() for c in line)


def _is_footer_or_signature(line):
    lower = line.lower()
    footer_markers = [
        "ocr output",
        "signature not",
        "signed by",
        "open the document in adobe",
        "courtesy: nic",
        "application no.",
        "order no.",
        "page ",
        "date :",
        "unadkat",
    ]
    return any(marker in lower for marker in footer_markers)


def _keep_keywords(doc_type):
    if doc_type == "lease":
        return [
            "lease",
            "lease deed",
            "lessor",
            "lessee",
            "owner",
            "company",
            "survey",
            "block",
            "area",
            "hectare",
            "sq",
            "acre",
            "duration",
            "year",
            "month",
            "agreement",
            "rent",
            "amount",
            "execute",
            "સરવે",
            "બ્લોક",
            "લીઝ",
            "ભાડા",
            "માલિક",
            "ક્ષેત્રફળ",
            "વર્ષ",
            "માસ",
            "કંપની",
            "અરજદાર",
        ]

    if doc_type == "na_order":
        return [
            "હુકમ",
            "પરિશિષ્ટ",
            "સરવે",
            "બ્લોક",
            "ક્ષેત્રફળ",
            "ચો.મી",
            "જમીન",
            "અરજદાર",
            "અધિકૃત",
            "કંપની",
            "તા.",
            "તારીખ",
            "વર્ષ",
            "માસ",
            "દિવસ",
            "survey",
            "block",
            "area",
            "company",
            "order",
            "date",
            "year",
            "month",
            "day",
        ]

    if doc_type == "echallan":
        return [
            "challan",
            "vehicle",
            "violation",
            "amount",
            "offence",
            "payment",
        ]

    return []


def _basic_clean_lines(text):
    lines = text.split("\n")
    cleaned = []
    seen_lines = set()

    for line in lines:
        line_stripped = line.strip()
        if len(line_stripped) <= 2:
            continue
        if not _contains_alnum(line_stripped):
            continue
        if _is_footer_or_signature(line_stripped):
            continue
        if line_stripped in seen_lines:
            continue

        seen_lines.add(line_stripped)
        cleaned.append(line_stripped)

    return cleaned


def clean_irrelevant_lines(text, doc_type):
    lines = _basic_clean_lines(text)
    if not lines:
        return ""

    keep_keywords = _keep_keywords(doc_type)
    if not keep_keywords:
        return "\n".join(lines)

    # Keep lines that contain strong document-specific keywords and keep local context.
    keep_indices = set()
    for i, line in enumerate(lines):
        lower = line.lower()
        if any(keyword in lower for keyword in keep_keywords):
            keep_indices.add(i)
            if i - 1 >= 0:
                keep_indices.add(i - 1)
            if i + 1 < len(lines):
                keep_indices.add(i + 1)

    # Fall back to basic cleaned lines if keyword matching is too sparse on noisy OCR.
    if len(keep_indices) < 5:
        return "\n".join(lines)

    selected = [lines[i] for i in sorted(keep_indices)]
    return "\n".join(selected)


def filter_pages(pages, doc_type):
    relevant = []

    for p in pages:
        text = p["text"]
        
        # Clean the text based on document type to remove irrelevant boilerplate
        cleaned_text = clean_irrelevant_lines(text, doc_type)

        if doc_type == "echallan":
            if "challan" in text.lower():
                relevant.append({"page": p["page"], "text": cleaned_text})

        elif doc_type == "lease":
            if (
                "survey" in text.lower()
                or "₹" in text
                or "amount" in text.lower()
                or "lessee" in text.lower()
                or "lease" in text.lower()
                or "લીઝ" in text
                or "સરવે" in text
            ):
                relevant.append({"page": p["page"], "text": cleaned_text})

        elif doc_type == "na_order":
            if "હુકમ" in text or "સર્વે" in text or "સરવે" in text or "પરિશિષ્ટ" in text:
                relevant.append({"page": p["page"], "text": cleaned_text})

        else:
            # fallback: keep first few pages
            if p["page"] <= 3:
                relevant.append({"page": p["page"], "text": cleaned_text})

    return relevant