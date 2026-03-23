import pdfplumber
import pytesseract
from pdf2image import convert_from_path


def clean_text(text):
    if not text:
        return ""
    return text.strip()


def is_garbage(text):
    return "(cid:" in text or len(text.strip()) < 20


def extract_text_pdfplumber(pdf_path):
    pages_text = []

    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            pages_text.append({
                "page": i + 1,
                "text": clean_text(text)
            })

    return pages_text


def extract_text_ocr_images(images, page_index):
    img = images[page_index]

    # Multi-language segmentation modes
    text_psm3 = pytesseract.image_to_string(
        img,
        lang="eng+hin+guj",
        config="--psm 3"
    )

    text_psm6 = pytesseract.image_to_string(
        img,
        lang="eng+hin+guj",
        config="--psm 6"
    )
    
    # Clean the spacing of both
    t3 = clean_text(text_psm3)
    t6 = clean_text(text_psm6)

    # Token Optimization: If the engine produced the exact same text for both PSM modes, 
    # only return one copy to avoid doubling the token cost.
    if t3 == t6:
        return t3

    # Return pure raw text (only for the distinct outputs).
    combined = f"--- OCR OUTPUT 1 ---\n{t3}\n\n--- OCR OUTPUT 2 ---\n{t6}"
    return clean_text(combined)


def hybrid_extract(pdf_path):
    pages = extract_text_pdfplumber(pdf_path)
    images = convert_from_path(pdf_path, dpi=300)

    final_pages = []

    for i, page in enumerate(pages):
        text = page["text"]

        if text and not is_garbage(text):
            final_pages.append(page)
        else:
            print(f"[INFO] Using OCR for page {page['page']}")
            ocr_text = extract_text_ocr_images(images, i)

            final_pages.append({
                "page": page["page"],
                "text": ocr_text
            })

    return final_pages