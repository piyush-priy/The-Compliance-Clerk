# NavSpark — Document Extraction Pipeline

A hybrid document extraction pipeline for processing legally dense, mixed-language (English + Gujarati) government documents — specifically **Non-Agricultural (NA) Orders** and **Lease Deeds**. The system extracts structured data from scanned PDFs, merges records by survey number, and exports a unified Excel spreadsheet.

## How It Works

The pipeline applies three extraction layers, in priority order:

1. **Deterministic Parser** — Regex-based extraction directly from PDF text or OCR output. Handles survey numbers, dates, areas, order numbers, and document numbers with high accuracy. This is the primary, most reliable layer.
2. **OCR Engine** — When `pdfplumber` returns garbled or empty text (e.g. scanned images), the system falls back to Tesseract OCR with OpenCV preprocessing (2× Lanczos upscaling, grayscale conversion) supporting English, Hindi, and Gujarati.
3. **LLM Fallback** — When deterministic extraction is insufficient, a compacted payload is sent to the Groq API (`llama-3.3-70b-versatile`) for structured field extraction. Deterministic values always override LLM output in the final merge.

```
PDF files (data/)
     │
     ▼
 ┌──────────────────────┐
 │  pdf_parser.py        │  pdfplumber → text, or OCR fallback
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  document_detector.py │  classify: na_order / lease
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  page_filter.py       │  strip noise, select relevant pages
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  lease_pipeline.py    │  deterministic lease extraction
 │  na_pipeline.py       │  deterministic NA order extraction
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  llm/extractor.py     │  LLM fallback (Groq API)
 └──────────┬───────────┘
            ▼
 ┌──────────────────────┐
 │  main.py              │  merge by survey number → XLSX + JSON
 └──────────────────────┘
```

## Project Structure

```
navspark/
├── main.py                       # Entry point — orchestrates the full pipeline
├── parser/
│   ├── pdf_parser.py             # PDF-to-text via pdfplumber; OCR fallback via
│   │                             #   pdf2image + OpenCV + pytesseract
│   ├── document_detector.py      # Classifies documents as na_order or lease
│   │                             #   (filename heuristics, then 5-page keyword scan)
│   ├── page_filter.py            # Strips OCR noise, footers, boilerplate; selects
│   │                             #   best OCR variant; keeps only signal-dense pages
│   ├── lease_pipeline.py         # Deterministic lease deed extraction — page
│   │                             #   classification, doc no, area, survey no,
│   │                             #   multi-page date consensus
│   └── na_pipeline.py            # Deterministic NA order extraction — Gujarati
│   │                             #   regex for order no, date, village, survey, area
├── llm/
│   ├── extractor.py              # Groq API client, token-budget management,
│   │                             #   smart text compaction, JSON parsing/repair
│   └── prompt.py                 # Few-shot prompts for lease and NA order extraction
├── schemas/
│   ├── lease.py                  # Pydantic model: LeaseRecord
│   └── na_order.py               # Pydantic model: NAOrder
├── storage/
│   └── logger.py                 # Logs every LLM prompt/response to logs/llm_logs.jsonl
├── data/                         # ⬅ Place input PDF files here
├── output/                       # ⬅ Generated outputs appear here
├── logs/                         # ⬅ LLM interaction logs (JSONL)
├── requirements.txt
├── .env                          # GROQ_API_KEY (not committed)
└── .gitignore
```

## Output

After processing, the `output/` directory contains:

| File | Description |
|------|-------------|
| `results.xlsx` | Unified spreadsheet with one row per survey number, merging NA and lease data |
| `results.json` | Same unified records as JSON |
| `document_records.json` | Full per-document extraction details (deterministic + LLM) |
| `*_parsed_pages.json` | Cleaned, filtered pages for each input PDF (debug) |
| `*_parsed_pages_raw.json` | Raw extracted pages before filtering (debug) |

The unified table has these columns:

| Sr.no. | Village | Survey No. | Area in NA Order | Dated | NA Order No. | Lease Deed Doc. No. | Lease Area | Lease Start |
|--------|---------|------------|------------------|-------|--------------|---------------------|------------|-------------|

## Setup

### System Dependencies

These must be installed separately (not via pip):

- **[Tesseract OCR](https://github.com/tesseract-ocr/tesseract)** — Install with language data for English (`eng`), Gujarati (`guj`), and Hindi (`hin`).
- **[Poppler](https://poppler.freedesktop.org/)** — Required by `pdf2image`. On Windows, add the Poppler `bin/` directory to your system `PATH`.

### Python Environment

```bash
# Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\activate        # Windows
source .venv/bin/activate     # macOS / Linux

# Install dependencies
pip install -r requirements.txt
```

### API Key

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key_here
```

## Usage

1. Place your PDF files in the `data/` directory.
2. Run the pipeline:

```bash
python main.py
```

3. Results appear in `output/results.xlsx` and `output/results.json`.

### File Naming Conventions

The parser uses filename patterns to supplement OCR-based extraction:

- **Lease Deeds** — Include the survey number and doc number in the filename:
  `Rampura Mota S.No.- 251p2 Lease Deed No.- 141.pdf`
- **NA Orders** — Use the survey number followed by `FINAL ORDER`:
  `251-p2 FINAL ORDER.pdf`

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `GROQ_API_KEY` | *(required)* | API key for the Groq LLM service |
| `MAX_REQUEST_TOKENS` | `1800` | Total token budget per LLM request |
| `MAX_INPUT_CHARS` | per-doc-type | Hard cap on input characters sent to LLM |
| `MAX_INPUT_CHARS_NA_ORDER` | `1000` | Character budget for NA order payloads |
| `MAX_INPUT_CHARS_LEASE` | `1200` | Character budget for lease payloads |
| `RESERVE_OUTPUT_TOKENS` | `350` | Tokens reserved for LLM response |
| `MAX_COMPLETION_TOKENS` | `350` | Max tokens the LLM may generate |
| `ENABLE_LLM_JSON_FIX` | `0` | Set to `1` to enable a second LLM call for JSON repair |

## Dependencies

```
python-dotenv   ≥1.0.0
pdfplumber      ≥0.10.3
pytesseract     ≥0.3.10
pdf2image       ≥1.16.3
opencv-python   ≥4.8.1
numpy           ≥1.26.0
openpyxl        ≥3.1.2
groq            ≥0.5.0
pydantic        ≥2.4.2
```
