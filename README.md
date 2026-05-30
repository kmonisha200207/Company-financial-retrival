# Equity Report Generator

An AI-powered web app that takes a company's financial context document and produces a downloadable **Geojit-style equity research PDF report** with tables, charts, and narrative sections.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18 + TypeScript + Vite |
| Backend | Python 3.11 + FastAPI |
| PDF generation | ReportLab |
| Charts | Matplotlib |
| AI extraction | OpenAI GPT-4o (falls back to regex heuristics) |
| Document parsing | pdfplumber (PDF), pandas (CSV), built-in (TXT) |

---

## Project Structure

```
EquityReportGenerator/
├── backend/
│   ├── main.py              # FastAPI app – POST /api/generate
│   ├── extractor.py         # AI + heuristic data extraction
│   ├── pdf_generator.py     # ReportLab PDF builder (all layout here)
│   ├── template_fields.py   # ← FIELD DEFINITIONS (edit to add fields)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── App.tsx           # Single-page UI
    │   └── main.tsx
    ├── index.html
    ├── package.json
    └── vite.config.ts
```

### Where template fields are defined

**`backend/template_fields.py`** is the single source of truth for all report fields:

- `TEMPLATE_FIELDS` – every field name, section, label, and default value.
- `FINANCIAL_TABLE_COLUMNS` – columns in the annual financial summary table.
- `QUARTERLY_TABLE_COLUMNS` – columns in the quarterly results table.

To **add a new field**: add an entry to `TEMPLATE_FIELDS`, reference it in `extractor.py`'s prompt, and render it in `pdf_generator.py`.

---

## How to Run

### 1. Backend

```bash
cd backend
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt

# (Optional) set your OpenAI key for AI extraction
copy .env.example .env        # Windows
# cp .env.example .env         # macOS/Linux
# Edit .env and set OPENAI_API_KEY=sk-...

uvicorn main:app --reload --port 8000
```

Backend runs at **http://localhost:8000**.  
API docs at **http://localhost:8000/docs**.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at **http://localhost:5173**.

### 3. Use the app

1. Open **http://localhost:5173**
2. Enter the company name.
3. Upload a financial document (PDF, TXT, or CSV).
4. Click **Generate & Download PDF**.

---

## Accepted Input Formats

| Format | Notes |
|--------|-------|
| PDF | Annual reports, investor presentations |
| TXT | Plain-text financial summaries |
| CSV | Financial data tables (revenue, margins, etc.) |

---

## Report Sections

1. **Header** – company name, ticker, sector, rating badge, CMP / target price / upside
2. **Key Stats Bar** – market cap, P/E, P/B, ROE, ROCE, D/E, dividend yield, 52W H/L
3. **Investment Highlights** – bullet points
4. **Company Overview** – narrative paragraph
5. **Financial Summary Table** – annual revenue, EBITDA, PAT, EPS, PE, PB, ROE
6. **Charts** – Revenue & PAT bar chart + Margin trend line chart
7. **Quarterly Results** – table + bar chart
8. **Investment Rationale / Recent Performance** – paragraphs
9. **Key Risks** + **Outlook & Recommendation** – two-column layout
10. **Footer** – disclaimer

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `OPENAI_API_KEY` | OpenAI API key for GPT-4o extraction | No (falls back to regex) |

---

## Adding a New Company / Field

1. Put the new field in `backend/template_fields.py → TEMPLATE_FIELDS`.
2. Add it to the JSON schema in `extractor.py → SYSTEM_PROMPT`.
3. Render it in `pdf_generator.py → generate_pdf()`.

No other files need to change.
