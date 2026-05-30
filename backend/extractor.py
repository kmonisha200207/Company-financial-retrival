"""
extractor.py – AI-powered data extraction from financial context documents.

Supports:
  • PDF  (via pdfplumber)
  • TXT
  • CSV  (pandas)
  • DOCX (python-docx, optional)

Uses OpenAI GPT-4o to map raw text → TEMPLATE_FIELDS structured JSON.
Falls back to a rule-based heuristic extractor when no API key is set.
"""

from __future__ import annotations

import io
import json
import os
import re
import traceback
from pathlib import Path
from typing import Any

import pandas as pd
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# ── helpers ──────────────────────────────────────────────────────────────────

def _read_pdf(file_bytes: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _read_csv(file_bytes: bytes) -> str:
    # Keep raw CSV text so comma-based parsers work correctly.
    # Also append a pandas summary for any narrative extraction.
    raw = file_bytes.decode("utf-8", errors="replace")
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
        summary = df.to_string(index=False)
        return raw + "\n\n--- PANDAS SUMMARY ---\n" + summary
    except Exception:
        return raw


def _read_txt(file_bytes: bytes) -> str:
    return file_bytes.decode("utf-8", errors="replace")


def extract_text(file_bytes: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _read_pdf(file_bytes)
    if ext == ".csv":
        return _read_csv(file_bytes)
    return _read_txt(file_bytes)


# ── prompt ───────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a financial analyst assistant. Extract structured data from the provided financial document text and return it as a single valid JSON object.

Return ONLY the JSON object (no markdown, no explanation).

The JSON must have EXACTLY these top-level keys:
{
  "company_name": "string",
  "ticker": "string",
  "sector": "string",
  "rating": "BUY | HOLD | SELL | ACCUMULATE",
  "target_price": "string (number only, e.g. '1250')",
  "cmp": "string (number only)",
  "upside": "string (percent, e.g. '18.5')",
  "market_cap": "string (number in Crores)",
  "report_date": "string (DD-MMM-YYYY)",
  "analyst": "string",
  "pe_ratio": "string",
  "pb_ratio": "string",
  "roe": "string",
  "roce": "string",
  "debt_equity": "string",
  "dividend_yield": "string",
  "52w_high": "string",
  "52w_low": "string",
  "company_overview": "2-4 sentence paragraph",
  "investment_rationale": "2-4 sentence paragraph",
  "recent_performance": "2-4 sentence paragraph about latest quarterly/annual results",
  "risks": "2-3 sentence paragraph",
  "outlook": "2-3 sentence paragraph with recommendation",
  "highlights": ["bullet 1", "bullet 2", "bullet 3", "bullet 4", "bullet 5"],
  "financial_table": [
    {"year":"FY22","revenue":"","ebitda":"","ebitda_margin":"","pat":"","eps":"","pe":"","pb":"","roe":""},
    {"year":"FY23","revenue":"","ebitda":"","ebitda_margin":"","pat":"","eps":"","pe":"","pb":"","roe":""},
    {"year":"FY24","revenue":"","ebitda":"","ebitda_margin":"","pat":"","eps":"","pe":"","pb":"","roe":""},
    {"year":"FY25E","revenue":"","ebitda":"","ebitda_margin":"","pat":"","eps":"","pe":"","pb":"","roe":""},
    {"year":"FY26E","revenue":"","ebitda":"","ebitda_margin":"","pat":"","eps":"","pe":"","pb":"","roe":""}
  ],
  "quarterly_table": [
    {"quarter":"Q1FY24","revenue":"","ebitda":"","pat":"","eps":""},
    {"quarter":"Q2FY24","revenue":"","ebitda":"","pat":"","eps":""},
    {"quarter":"Q3FY24","revenue":"","ebitda":"","pat":"","eps":""},
    {"quarter":"Q4FY24","revenue":"","ebitda":"","pat":"","eps":""},
    {"quarter":"Q1FY25","revenue":"","ebitda":"","pat":"","eps":""}
  ]
}

Rules:
- Fill every field with real data from the document wherever possible.
- If a value cannot be found, use "" (empty string) for string fields, [] for arrays.
- Do NOT invent numbers you cannot find in the document.
- All monetary values should be numbers only (no ₹ / Rs / Cr suffix).
- Percentages should be numbers only (no % suffix).
"""


# ── AI extraction ─────────────────────────────────────────────────────────────

def _extract_with_openai(text: str, company_name: str) -> dict[str, Any]:
    import openai  # lazy import so app still starts without openai installed
    client = openai.OpenAI(api_key=OPENAI_API_KEY)
    user_msg = f"Company: {company_name}\n\n--- DOCUMENT ---\n{text[:12000]}"
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_msg},
        ],
        temperature=0.1,
        max_tokens=3000,
    )
    raw = response.choices[0].message.content.strip()
    # strip accidental markdown fences
    raw = re.sub(r"^```(?:json)?", "", raw).strip()
    raw = re.sub(r"```$", "", raw).strip()
    return json.loads(raw)


# ── rule-based fallback ───────────────────────────────────────────────────────

_NUM = r"[\d,]+(?:\.\d+)?"

def _find(pattern: str, text: str, default: str = "") -> str:
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).replace(",", "").strip() if m else default


def _parse_fin_line(line: str) -> dict | None:
    """Parse a line like: FY22: Revenue=792756, EBITDA=136790, ..."""
    year_m = re.match(r"(FY\d{2}E?|FY\d{4}E?)", line, re.IGNORECASE)
    if not year_m:
        return None
    row: dict[str, str] = {"year": year_m.group(1)}
    for key, pat in [
        ("revenue",       r"revenue[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("ebitda",        r"ebitda[=:\s]*([\d,]+(?:\.\d+)?)(?!\s*margin)"),
        ("ebitda_margin", r"ebitda[_\s]*margin[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("pat",           r"pat[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("eps",           r"eps[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("pe",            r"pe[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("pb",            r"pb[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("roe",           r"roe[=:\s]*([\d,]+(?:\.\d+)?)"),
    ]:
        m = re.search(pat, line, re.IGNORECASE)
        row[key] = m.group(1).replace(",", "") if m else ""
    return row


def _parse_quarterly_line(line: str) -> dict | None:
    """Parse a line like: Q1FY24: Revenue=37933, EBITDA=9540, PAT=6315, EPS=15.1"""
    q_m = re.match(r"(Q[1-4]FY\d{2,4})", line, re.IGNORECASE)
    if not q_m:
        return None
    row: dict[str, str] = {"quarter": q_m.group(1)}
    for key, pat in [
        ("revenue", r"revenue[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("ebitda",  r"ebitda[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("pat",     r"pat[=:\s]*([\d,]+(?:\.\d+)?)"),
        ("eps",     r"eps[=:\s]*([\d,]+(?:\.\d+)?)"),
    ]:
        m = re.search(pat, line, re.IGNORECASE)
        row[key] = m.group(1).replace(",", "") if m else ""
    return row


def _parse_csv_tables(text: str) -> tuple[list[dict], list[dict]]:
    """Extract financial + quarterly tables from CSV text using pandas."""
    fin_rows:  list[dict] = []
    q_rows:    list[dict] = []

    # ── quarterly table: rows starting with Q1/Q2/Q3/Q4 ─────────────────────
    q_lines: list[str] = []
    header_line = ""
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if re.match(r"quarter", parts[0], re.IGNORECASE):
            header_line = line
        elif re.match(r"Q[1-4]FY", parts[0], re.IGNORECASE) and len(parts) >= 4:
            # only if at least revenue value is numeric
            rev = parts[1] if len(parts) > 1 else ""
            if not re.match(r"^[\d,]+(?:\.\d+)?$", rev.strip()):
                continue
            q_lines.append(line)
    if q_lines:
        for line in q_lines:
            p = [x.strip() for x in line.split(",")]
            q_rows.append({
                "quarter": p[0],
                "revenue": p[1] if len(p) > 1 else "",
                "ebitda":  p[2] if len(p) > 2 else "",
                "pat":     p[3] if len(p) > 3 else "",
                "eps":     p[4] if len(p) > 4 else "",
            })

    # ── annual table: Company,Metric,FY22,FY23,FY24,FY25E,FY26E format ──────
    # First pass: collect year labels from any header row containing FYxx
    year_labels: list[str] = []
    metric_data: dict[str, list[str]] = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        # detect year header row (first column is "Company" or blank, has FYxx entries)
        fy_cols = [p for p in parts if re.match(r"FY\d{2}", p, re.IGNORECASE)]
        if len(fy_cols) >= 3 and not year_labels:
            year_labels = fy_cols
            continue
        # metric rows: Company, MetricName, val1, val2, ...
        if len(parts) >= 4 and year_labels:
            metric_cell = parts[1].lower() if len(parts) > 1 else ""
            values = parts[2: 2 + len(year_labels)]
            # only accept if first value looks numeric (skip header/label rows)
            if not values or not re.match(r"^-?[\d,]+(?:\.\d+)?$", values[0].strip()):
                continue
            for key_frag, field in [
                ("revenue",        "revenue"),
                ("ebitda margin",  "ebitda_margin"),
                ("ebitda",         "ebitda"),
                ("pat",            "pat"),
                ("eps",            "eps"),
                ("p/e",            "pe"),
                ("p/b",            "pb"),
                ("roe",            "roe"),
            ]:
                if key_frag in metric_cell:
                    metric_data[field] = values
                    break

    if year_labels and metric_data:
        for i, yr in enumerate(year_labels):
            row: dict[str, str] = {"year": yr}
            for field in ("revenue","ebitda","ebitda_margin","pat","eps","pe","pb","roe"):
                vals = metric_data.get(field, [])
                raw = vals[i].replace(",","").strip() if i < len(vals) else ""
                # strip trailing % or units
                raw = re.sub(r"[%₹\s].*$", "", raw)
                row[field] = raw
            fin_rows.append(row)

    # ── key metrics from Company,Detail,Value rows ────────────────────────────
    kv: dict[str, str] = {}
    for line in text.splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) >= 3 and parts[2]:
            kv[parts[1].lower()] = parts[2]

    return fin_rows, q_rows, kv


def _kv_get(kv: dict[str, str], *fragments: str) -> str:
    for frag in fragments:
        for k, v in kv.items():
            if frag.lower() in k:
                return v.replace(",", "").strip()
    return ""


def _extract_sections(text: str) -> dict[str, str]:
    """Pull named sections delimited by --- SECTION NAME --- markers."""
    sections: dict[str, str] = {}
    pattern = r"---\s*([A-Z\s]+?)\s*---\s*\n(.*?)(?=---|\Z)"
    for m in re.finditer(pattern, text, re.DOTALL):
        key = m.group(1).strip().lower().replace(" ", "_")
        sections[key] = m.group(2).strip()
    return sections


def _extract_heuristic(text: str, company_name: str) -> dict[str, Any]:
    """Enhanced regex-based extraction supporting structured TXT and CSV formats."""
    sections = _extract_sections(text)

    data: dict[str, Any] = {
        "company_name":         company_name or _find(r"(?:company|name)[:\s]+([A-Z][A-Za-z\s&.]+)", text),
        "ticker":               _find(r"(?:NSE\s*Code|BSE|Ticker)[:\s]+([A-Z0-9]+)", text),
        "sector":               _find(r"sector[:\s]+([A-Za-z &/,]+)", text),
        "rating":               _find(r"\b(BUY|HOLD|SELL|ACCUMULATE|REDUCE)\b", text, "BUY"),
        "target_price":         _find(r"[Tt]arget\s*[Pp]rice[:\s₹Rs.]*(" + _NUM + ")", text),
        "cmp":                  _find(r"(?:CMP|current\s*market\s*price)[:\s₹Rs.]*(" + _NUM + ")", text),
        "upside":               _find(r"[Uu]pside[:\s]*(" + _NUM + r")\s*%?", text),
        "market_cap":           _find(r"[Mm]arket\s*[Cc]ap[:\s₹Rs.Cr]*(" + _NUM + ")", text),
        "report_date":          _find(r"[Dd]ate[:\s]+(\d{1,2}[- /][A-Za-z]{3}[- /]\d{2,4})", text),
        "analyst":              _find(r"[Aa]nalyst[:\s]+([A-Za-z\s.]+?)(?:\n|$)", text, "Research Desk"),
        "pe_ratio":             _find(r"P/E(?:\s*\(TTM\))?[:\s]*(" + _NUM + ")", text),
        "pb_ratio":             _find(r"P/B[:\s]*(" + _NUM + ")", text),
        "roe":                  _find(r"ROE[:\s]*(" + _NUM + r")\s*%?", text),
        "roce":                 _find(r"ROCE[:\s]*(" + _NUM + r")\s*%?", text),
        "debt_equity":          _find(r"D(?:ebt)?[/\-]E(?:quity)?[:\s]*(" + _NUM + ")", text),
        "dividend_yield":       _find(r"[Dd]ividend\s*[Yy]ield[:\s]*(" + _NUM + r")\s*%?", text),
        "52w_high":             _find(r"52[- ]?[Ww](?:eek)?\s*[Hh]igh[:\s₹Rs.]*(" + _NUM + ")", text),
        "52w_low":              _find(r"52[- ]?[Ww](?:eek)?\s*[Ll]ow[:\s₹Rs.]*(" + _NUM + ")", text),
        "company_overview":     sections.get("company_overview", ""),
        "investment_rationale": sections.get("investment_rationale", ""),
        "recent_performance":   sections.get("recent_performance", ""),
        "risks":                sections.get("key_risks", ""),
        "outlook":              sections.get("outlook", ""),
        "highlights":           [],
        "financial_table":      [],
        "quarterly_table":      [],
    }

    # ── financial table: structured TXT lines ────────────────────────────────
    fin_section = sections.get("financial_data", "")
    for line in (fin_section or text).splitlines():
        row = _parse_fin_line(line)
        if row:
            data["financial_table"].append(row)

    # ── quarterly table: structured TXT lines ────────────────────────────────
    q_section = sections.get("quarterly_data", "")
    for line in (q_section or text).splitlines():
        row = _parse_quarterly_line(line)
        if row:
            data["quarterly_table"].append(row)

    # ── CSV tables fallback ───────────────────────────────────────────────────
    # Use CSV parser if financial table is empty OR quarterly table has no revenue values
    _q_has_data = any(r.get("revenue") for r in data["quarterly_table"])
    if not data["financial_table"] or not _q_has_data:
        csv_fin, csv_q, kv = _parse_csv_tables(text)
        if not data["financial_table"]:
            data["financial_table"] = csv_fin
        if not data["quarterly_table"] or not _q_has_data:
            data["quarterly_table"] = csv_q
        # backfill scalar metrics from CSV key-value pairs
        if kv:
            if not data["cmp"]:          data["cmp"]          = _kv_get(kv, "cmp", "current market")
            if not data["target_price"]: data["target_price"] = _kv_get(kv, "target price", "target")
            if not data["upside"]:       data["upside"]       = _kv_get(kv, "upside")
            if not data["rating"]:       data["rating"]       = _kv_get(kv, "rating")
            if not data["market_cap"]:   data["market_cap"]   = _kv_get(kv, "market cap")
            if not data["ticker"]:       data["ticker"]       = _kv_get(kv, "ticker", "nse")
            if not data["sector"]:       data["sector"]       = _kv_get(kv, "sector")
            if not data["pe_ratio"]:     data["pe_ratio"]     = _kv_get(kv, "p/e")
            if not data["pb_ratio"]:     data["pb_ratio"]     = _kv_get(kv, "p/b")
            if not data["roe"]:          data["roe"]          = _kv_get(kv, "roe")
            if not data["roce"]:         data["roce"]         = _kv_get(kv, "roce")
            if not data["debt_equity"]:  data["debt_equity"]  = _kv_get(kv, "debt")
            if not data["dividend_yield"]: data["dividend_yield"] = _kv_get(kv, "dividend")
            if not data["52w_high"]:     data["52w_high"]     = _kv_get(kv, "52w high", "52 week high")
            if not data["52w_low"]:      data["52w_low"]      = _kv_get(kv, "52w low",  "52 week low")

    # ── fallback: pull paragraphs when sections not marked ───────────────────
    if not data["company_overview"]:
        paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80
                 and not p.strip().startswith("---")]
        if paras:     data["company_overview"]     = paras[0][:700]
        if len(paras) > 1: data["investment_rationale"] = paras[1][:700]
        if len(paras) > 2: data["recent_performance"]   = paras[2][:700]

    return data


# ── public API ────────────────────────────────────────────────────────────────

def extract_data(file_bytes: bytes, filename: str, company_name: str) -> dict[str, Any]:
    """Main entry point. Returns a dict matching TEMPLATE_FIELDS keys."""
    text = extract_text(file_bytes, filename)

    if OPENAI_API_KEY:
        try:
            return _extract_with_openai(text, company_name)
        except Exception:
            traceback.print_exc()
            print("[extractor] OpenAI failed, falling back to heuristic extraction")

    return _extract_heuristic(text, company_name)
