# Template field definitions for the Geojit-style equity research report.
# Each field maps to a section/cell in the PDF template.
# Modify this file to add new fields or companies.

TEMPLATE_FIELDS = {
    # ── Header ──────────────────────────────────────────────────────────────
    "company_name":       {"section": "header",  "label": "Company Name",        "default": "N/A"},
    "ticker":             {"section": "header",  "label": "Ticker / NSE Code",   "default": "N/A"},
    "sector":             {"section": "header",  "label": "Sector",              "default": "N/A"},
    "rating":             {"section": "header",  "label": "Rating",              "default": "BUY"},
    "target_price":       {"section": "header",  "label": "Target Price (₹)",    "default": "N/A"},
    "cmp":                {"section": "header",  "label": "CMP (₹)",             "default": "N/A"},
    "upside":             {"section": "header",  "label": "Upside (%)",          "default": "N/A"},
    "market_cap":         {"section": "header",  "label": "Market Cap (₹ Cr)",   "default": "N/A"},
    "report_date":        {"section": "header",  "label": "Date",                "default": "N/A"},
    "analyst":            {"section": "header",  "label": "Analyst",             "default": "Research Desk"},

    # ── Key Metrics (single-value) ───────────────────────────────────────────
    "pe_ratio":           {"section": "metrics", "label": "P/E (TTM)",           "default": "N/A"},
    "pb_ratio":           {"section": "metrics", "label": "P/B",                 "default": "N/A"},
    "roe":                {"section": "metrics", "label": "ROE (%)",             "default": "N/A"},
    "roce":               {"section": "metrics", "label": "ROCE (%)",            "default": "N/A"},
    "debt_equity":        {"section": "metrics", "label": "Debt/Equity",         "default": "N/A"},
    "dividend_yield":     {"section": "metrics", "label": "Dividend Yield (%)",  "default": "N/A"},
    "52w_high":           {"section": "metrics", "label": "52W High (₹)",        "default": "N/A"},
    "52w_low":            {"section": "metrics", "label": "52W Low (₹)",         "default": "N/A"},

    # ── Narrative Sections ───────────────────────────────────────────────────
    "company_overview":   {"section": "narrative", "label": "Company Overview",        "default": ""},
    "investment_rationale":{"section": "narrative","label": "Investment Rationale",    "default": ""},
    "recent_performance": {"section": "narrative", "label": "Recent Performance",      "default": ""},
    "risks":              {"section": "narrative", "label": "Key Risks",               "default": ""},
    "outlook":            {"section": "narrative", "label": "Outlook & Recommendation","default": ""},

    # ── Investment Highlights (bullet list) ──────────────────────────────────
    "highlights":         {"section": "bullets",  "label": "Investment Highlights",   "default": []},

    # ── Financial Summary Table (list of dicts, one row per year) ────────────
    # Expected keys per row: year, revenue, ebitda, ebitda_margin, pat, eps, pe, pb, roe
    "financial_table":    {"section": "table",   "label": "Financial Summary",        "default": []},

    # ── Quarterly Results Table (list of dicts) ──────────────────────────────
    # Expected keys per row: quarter, revenue, ebitda, pat, eps
    "quarterly_table":    {"section": "table",   "label": "Quarterly Results",        "default": []},

    # ── Charts (auto-generated from financial_table / quarterly_table) ───────
    "chart_revenue":      {"section": "chart",   "label": "Revenue Trend",            "default": None},
    "chart_margins":      {"section": "chart",   "label": "Margin Trend",             "default": None},
    "chart_pat":          {"section": "chart",   "label": "PAT Trend",                "default": None},
}

# Columns expected in financial_table rows
FINANCIAL_TABLE_COLUMNS = [
    ("year",           "Year"),
    ("revenue",        "Revenue\n(₹ Cr)"),
    ("ebitda",         "EBITDA\n(₹ Cr)"),
    ("ebitda_margin",  "EBITDA\nMargin (%)"),
    ("pat",            "PAT\n(₹ Cr)"),
    ("eps",            "EPS (₹)"),
    ("pe",             "P/E (x)"),
    ("pb",             "P/B (x)"),
    ("roe",            "ROE (%)"),
]

# Columns expected in quarterly_table rows
QUARTERLY_TABLE_COLUMNS = [
    ("quarter",  "Quarter"),
    ("revenue",  "Revenue\n(₹ Cr)"),
    ("ebitda",   "EBITDA\n(₹ Cr)"),
    ("pat",      "PAT\n(₹ Cr)"),
    ("eps",      "EPS (₹)"),
]
