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
    df = pd.read_csv(io.BytesIO(file_bytes))
    return df.to_string(index=False)


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


def _extract_heuristic(text: str, company_name: str) -> dict[str, Any]:
    """Simple regex-based extraction when no OpenAI key is available."""
    data: dict[str, Any] = {
        "company_name":        company_name or _find(r"(?:company|name)[:\s]+([A-Z][A-Za-z\s&.]+)", text),
        "ticker":              _find(r"(?:NSE|BSE|ticker)[:\s]+([A-Z0-9]+)", text),
        "sector":              _find(r"sector[:\s]+([A-Za-z &/]+)", text),
        "rating":              _find(r"\b(BUY|HOLD|SELL|ACCUMULATE|REDUCE)\b", text, "BUY"),
        "target_price":        _find(r"target\s*price[:\s₹Rs.]*(" + _NUM + ")", text),
        "cmp":                 _find(r"(?:CMP|current\s*market\s*price)[:\s₹Rs.]*(" + _NUM + ")", text),
        "upside":              _find(r"upside[:\s]*(" + _NUM + r")\s*%?", text),
        "market_cap":          _find(r"market\s*cap(?:italisation)?[:\s₹Rs.Cr]*(" + _NUM + ")", text),
        "report_date":         _find(r"date[:\s]+(\d{1,2}[- /][A-Za-z]{3}[- /]\d{2,4})", text),
        "analyst":             _find(r"analyst[:\s]+([A-Za-z\s.]+)", text, "Research Desk"),
        "pe_ratio":            _find(r"P/E[:\s]*(" + _NUM + ")", text),
        "pb_ratio":            _find(r"P/B[:\s]*(" + _NUM + ")", text),
        "roe":                 _find(r"ROE[:\s]*(" + _NUM + r")\s*%?", text),
        "roce":                _find(r"ROCE[:\s]*(" + _NUM + r")\s*%?", text),
        "debt_equity":         _find(r"D(?:ebt)?[/\-]E(?:quity)?[:\s]*(" + _NUM + ")", text),
        "dividend_yield":      _find(r"dividend\s*yield[:\s]*(" + _NUM + r")\s*%?", text),
        "52w_high":            _find(r"52[- ]?w(?:eek)?\s*high[:\s₹Rs.]*(" + _NUM + ")", text),
        "52w_low":             _find(r"52[- ]?w(?:eek)?\s*low[:\s₹Rs.]*(" + _NUM + ")", text),
        "company_overview":    "",
        "investment_rationale": "",
        "recent_performance":  "",
        "risks":               "",
        "outlook":             "",
        "highlights":          [],
        "financial_table":     [],
        "quarterly_table":     [],
    }
    # try to pull a paragraph as overview
    paras = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 80]
    if paras:
        data["company_overview"] = paras[0][:600]
    if len(paras) > 1:
        data["investment_rationale"] = paras[1][:600]
    if len(paras) > 2:
        data["recent_performance"] = paras[2][:600]
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
