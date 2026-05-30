"""
pdf_generator.py – Generates a Geojit-style equity research report PDF using ReportLab.

Layout (top → bottom):
  1. Header band  – company name, ticker, rating badge, CMP / TP / upside
  2. Key stats bar – market cap, PE, PB, ROE, ROCE, D/E, div yield, 52W H/L
  3. Investment Highlights (bullets)
  4. Company Overview (paragraph)
  5. Financial Summary table (annual)
  6. Revenue & PAT bar chart  +  EBITDA margin line chart
  7. Quarterly Results table
  8. Investment Rationale / Recent Performance (paragraphs)
  9. Key Risks  +  Outlook & Recommendation
 10. Footer disclaimer
"""

from __future__ import annotations

import io
import math
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    Image,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.flowables import HRFlowable

from template_fields import FINANCIAL_TABLE_COLUMNS, QUARTERLY_TABLE_COLUMNS

# ── Brand colours (Geojit palette) ───────────────────────────────────────────
C_DARK_BLUE  = colors.HexColor("#003366")
C_MID_BLUE   = colors.HexColor("#1565C0")
C_LIGHT_BLUE = colors.HexColor("#E3F0FF")
C_ORANGE     = colors.HexColor("#E65100")
C_GREEN      = colors.HexColor("#1B5E20")
C_GREEN_LIGHT= colors.HexColor("#E8F5E9")
C_RED        = colors.HexColor("#B71C1C")
C_RED_LIGHT  = colors.HexColor("#FFEBEE")
C_GREY_HEAD  = colors.HexColor("#37474F")
C_GREY_ROW   = colors.HexColor("#F5F5F5")
C_WHITE      = colors.white
C_BLACK      = colors.black

PAGE_W, PAGE_H = A4
MARGIN = 1.5 * cm
CONTENT_W = PAGE_W - 2 * MARGIN


# ── Style sheet ───────────────────────────────────────────────────────────────
_base = getSampleStyleSheet()

def _style(name, **kw) -> ParagraphStyle:
    return ParagraphStyle(name, **kw)

S_TITLE   = _style("title",   fontSize=18, leading=22, textColor=C_DARK_BLUE,
                    fontName="Helvetica-Bold", alignment=TA_LEFT)
S_TICKER  = _style("ticker",  fontSize=11, leading=14, textColor=C_GREY_HEAD,
                    fontName="Helvetica")
S_SECTION = _style("section", fontSize=10, leading=13, textColor=C_WHITE,
                    fontName="Helvetica-Bold", alignment=TA_LEFT,
                    spaceAfter=2, leftIndent=4)
S_BODY    = _style("body",    fontSize=8.5, leading=12, textColor=C_BLACK,
                    fontName="Helvetica", alignment=TA_JUSTIFY, spaceAfter=4)
S_BULLET  = _style("bullet",  fontSize=8.5, leading=12, textColor=C_BLACK,
                    fontName="Helvetica", leftIndent=12, bulletIndent=4,
                    spaceAfter=2)
S_SMALL   = _style("small",   fontSize=7, leading=9, textColor=colors.grey,
                    fontName="Helvetica", alignment=TA_CENTER)
S_BOLD    = _style("bold",    fontSize=8.5, leading=12, textColor=C_DARK_BLUE,
                    fontName="Helvetica-Bold")
S_BADGE_BUY  = _style("badge_buy",  fontSize=11, leading=14, textColor=C_WHITE,
                        fontName="Helvetica-Bold", alignment=TA_CENTER)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe(val: Any, suffix: str = "") -> str:
    if val is None or str(val).strip() == "":
        return "—"
    return f"{val}{suffix}"


def _section_header(title: str, width: float) -> Table:
    """Coloured section header bar."""
    p = Paragraph(title.upper(), S_SECTION)
    t = Table([[p]], colWidths=[width])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), C_DARK_BLUE),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
    ]))
    return t


def _rating_color(rating: str) -> colors.Color:
    r = str(rating).upper()
    if r in ("BUY", "ACCUMULATE"):
        return C_GREEN
    if r in ("SELL", "REDUCE"):
        return C_RED
    return C_MID_BLUE


# ── Chart builders ────────────────────────────────────────────────────────────

def _fig_to_image(fig, width: float, height: float) -> Image:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=150, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return Image(buf, width=width, height=height)


def _chart_revenue_pat(fin_rows: list[dict]) -> Image | None:
    if not fin_rows:
        return None
    years   = [r.get("year", "") for r in fin_rows]
    revenue = [_to_float(r.get("revenue")) for r in fin_rows]
    pat     = [_to_float(r.get("pat"))     for r in fin_rows]

    x = np.arange(len(years))
    w = 0.35
    fig, ax = plt.subplots(figsize=(5.5, 3))
    ax.bar(x - w/2, revenue, w, label="Revenue", color="#1565C0", alpha=0.85)
    ax.bar(x + w/2, pat,     w, label="PAT",     color="#43A047", alpha=0.85)
    ax.set_xticks(x); ax.set_xticklabels(years, fontsize=8)
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    ax.set_ylabel("₹ Cr", fontsize=8)
    ax.set_title("Revenue & PAT (₹ Cr)", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _fig_to_image(fig, width=8.5*cm, height=5.5*cm)


def _chart_margins(fin_rows: list[dict]) -> Image | None:
    if not fin_rows:
        return None
    years  = [r.get("year", "") for r in fin_rows]
    ebitda = [_to_float(r.get("ebitda_margin")) for r in fin_rows]
    pat_m  = []
    for r in fin_rows:
        rev = _to_float(r.get("revenue"))
        pat = _to_float(r.get("pat"))
        if rev and rev != 0:
            pat_m.append(round(pat / rev * 100, 1))
        else:
            pat_m.append(0.0)

    fig, ax = plt.subplots(figsize=(5.5, 3))
    x = np.arange(len(years))
    ax.plot(x, ebitda, marker="o", color="#E65100", linewidth=2, label="EBITDA Margin %")
    ax.plot(x, pat_m,  marker="s", color="#1565C0", linewidth=2, label="PAT Margin %")
    ax.set_xticks(x); ax.set_xticklabels(years, fontsize=8)
    ax.set_ylabel("%", fontsize=8)
    ax.set_title("Margin Trends (%)", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _fig_to_image(fig, width=8.5*cm, height=5.5*cm)


def _chart_quarterly(q_rows: list[dict]) -> Image | None:
    if not q_rows:
        return None
    quarters = [r.get("quarter", "") for r in q_rows]
    revenue  = [_to_float(r.get("revenue")) for r in q_rows]
    pat      = [_to_float(r.get("pat"))     for r in q_rows]

    x = np.arange(len(quarters))
    w = 0.35
    fig, ax = plt.subplots(figsize=(CONTENT_W / (2.54 * 2.5), 3))
    ax.bar(x - w/2, revenue, w, label="Revenue", color="#1565C0", alpha=0.85)
    ax.bar(x + w/2, pat,     w, label="PAT",     color="#43A047", alpha=0.85)
    ax.set_xticks(x); ax.set_xticklabels(quarters, fontsize=7, rotation=30, ha="right")
    ax.set_ylabel("₹ Cr", fontsize=8)
    ax.set_title("Quarterly Revenue & PAT (₹ Cr)", fontsize=9, fontweight="bold")
    ax.legend(fontsize=8)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    return _fig_to_image(fig, width=CONTENT_W * 0.55, height=5*cm)


def _to_float(v: Any) -> float:
    try:
        return float(str(v).replace(",", ""))
    except Exception:
        return 0.0


# ── Table builders ────────────────────────────────────────────────────────────

def _financial_table(fin_rows: list[dict]) -> Table:
    col_keys  = [c[0] for c in FINANCIAL_TABLE_COLUMNS]
    col_heads = [c[1] for c in FINANCIAL_TABLE_COLUMNS]
    n_cols    = len(col_keys)
    col_w     = CONTENT_W / n_cols

    header = [Paragraph(h, _style(f"th{i}", fontSize=7.5, leading=10,
                fontName="Helvetica-Bold", textColor=C_WHITE, alignment=TA_CENTER))
              for i, h in enumerate(col_heads)]
    rows = [header]
    for i, r in enumerate(fin_rows):
        bg = C_GREY_ROW if i % 2 == 0 else C_WHITE
        row = [Paragraph(_safe(r.get(k)), _style(f"td{i}{j}", fontSize=7.5, leading=10,
                    fontName="Helvetica", textColor=C_BLACK, alignment=TA_CENTER))
               for j, k in enumerate(col_keys)]
        rows.append(row)

    t = Table(rows, colWidths=[col_w] * n_cols, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), C_MID_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_GREY_ROW, C_WHITE]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ])
    t.setStyle(style)
    return t


def _quarterly_table(q_rows: list[dict]) -> Table:
    col_keys  = [c[0] for c in QUARTERLY_TABLE_COLUMNS]
    col_heads = [c[1] for c in QUARTERLY_TABLE_COLUMNS]
    n_cols    = len(col_keys)
    col_w     = CONTENT_W / n_cols

    header = [Paragraph(h, _style(f"qth{i}", fontSize=7.5, leading=10,
                fontName="Helvetica-Bold", textColor=C_WHITE, alignment=TA_CENTER))
              for i, h in enumerate(col_heads)]
    rows = [header]
    for i, r in enumerate(q_rows):
        row = [Paragraph(_safe(r.get(k)), _style(f"qtd{i}{j}", fontSize=7.5, leading=10,
                    fontName="Helvetica", textColor=C_BLACK, alignment=TA_CENTER))
               for j, k in enumerate(col_keys)]
        rows.append(row)

    t = Table(rows, colWidths=[col_w] * n_cols, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1,  0), C_MID_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [C_GREY_ROW, C_WHITE]),
        ("GRID",          (0, 0), (-1, -1), 0.4, colors.lightgrey),
        ("TOPPADDING",    (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    return t


def _header_table(data: dict) -> Table:
    """Top header block: company name | rating badge | CMP/TP/upside."""
    rating    = _safe(data.get("rating", "BUY"))
    r_color   = _rating_color(rating)
    cmp_val   = _safe(data.get("cmp"), "")
    tp_val    = _safe(data.get("target_price"), "")
    upside    = _safe(data.get("upside"), "%")

    name_para = Paragraph(data.get("company_name", "Company"), S_TITLE)
    tick_para = Paragraph(
        f"{_safe(data.get('ticker'))}  |  {_safe(data.get('sector'))}  |  {_safe(data.get('report_date'))}",
        S_TICKER)

    rating_para = Paragraph(rating, _style("rb", fontSize=13, leading=16,
        fontName="Helvetica-Bold", textColor=C_WHITE, alignment=TA_CENTER))
    rating_cell = Table([[rating_para]], colWidths=[2.5*cm])
    rating_cell.setStyle(TableStyle([
        ("BACKGROUND", (0,0),(-1,-1), r_color),
        ("TOPPADDING", (0,0),(-1,-1), 8),
        ("BOTTOMPADDING",(0,0),(-1,-1), 8),
        ("ROUNDEDCORNERS", [4]),
    ]))

    price_data = [
        [Paragraph("CMP",    _style("pl", fontSize=7,  fontName="Helvetica", textColor=colors.grey, alignment=TA_CENTER)),
         Paragraph("Target", _style("pl", fontSize=7,  fontName="Helvetica", textColor=colors.grey, alignment=TA_CENTER)),
         Paragraph("Upside", _style("pl", fontSize=7,  fontName="Helvetica", textColor=colors.grey, alignment=TA_CENTER))],
        [Paragraph(f"₹{cmp_val}", _style("pv", fontSize=11, fontName="Helvetica-Bold", textColor=C_DARK_BLUE, alignment=TA_CENTER)),
         Paragraph(f"₹{tp_val}", _style("pv2", fontSize=11, fontName="Helvetica-Bold", textColor=C_DARK_BLUE, alignment=TA_CENTER)),
         Paragraph(f"{upside}",  _style("pv3", fontSize=11, fontName="Helvetica-Bold", textColor=C_GREEN,     alignment=TA_CENTER))],
    ]
    price_tbl = Table(price_data, colWidths=[2.8*cm, 2.8*cm, 2.8*cm])
    price_tbl.setStyle(TableStyle([
        ("ALIGN",         (0,0),(-1,-1), "CENTER"),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LINEBELOW",     (0,0),(-1,0),  0.5, colors.lightgrey),
    ]))

    left_col  = [name_para, Spacer(1, 2), tick_para]
    # nest left col items in a mini-table for alignment
    left_tbl = Table([[item] for item in left_col], colWidths=[CONTENT_W - 9*cm])
    left_tbl.setStyle(TableStyle([
        ("TOPPADDING",    (0,0),(-1,-1), 2),
        ("BOTTOMPADDING", (0,0),(-1,-1), 2),
    ]))

    main = Table(
        [[left_tbl, rating_cell, price_tbl]],
        colWidths=[CONTENT_W - 9*cm, 3*cm, 6*cm],
    )
    main.setStyle(TableStyle([
        ("VALIGN",        (0,0),(-1,-1), "MIDDLE"),
        ("BACKGROUND",    (0,0),(-1,-1), C_LIGHT_BLUE),
        ("TOPPADDING",    (0,0),(-1,-1), 8),
        ("BOTTOMPADDING", (0,0),(-1,-1), 8),
        ("LEFTPADDING",   (0,0),(-1,-1), 8),
        ("RIGHTPADDING",  (0,0),(-1,-1), 8),
        ("LINEBELOW",     (0,0),(-1,-1), 1.5, C_DARK_BLUE),
    ]))
    return main


def _stats_bar(data: dict) -> Table:
    """Single-row key statistics strip."""
    fields = [
        ("Mkt Cap (₹ Cr)", data.get("market_cap")),
        ("P/E (TTM)",       data.get("pe_ratio")),
        ("P/B",             data.get("pb_ratio")),
        ("ROE (%)",         data.get("roe")),
        ("ROCE (%)",        data.get("roce")),
        ("D/E",             data.get("debt_equity")),
        ("Div Yield (%)",   data.get("dividend_yield")),
        ("52W H / L",       f"{_safe(data.get('52w_high'))} / {_safe(data.get('52w_low'))}"),
    ]
    label_row = []
    value_row = []
    for lbl, val in fields:
        label_row.append(Paragraph(lbl, _style(f"sl{lbl}", fontSize=7, leading=9,
            fontName="Helvetica", textColor=colors.grey, alignment=TA_CENTER)))
        value_row.append(Paragraph(_safe(val), _style(f"sv{lbl}", fontSize=8.5, leading=11,
            fontName="Helvetica-Bold", textColor=C_DARK_BLUE, alignment=TA_CENTER)))
    col_w = CONTENT_W / len(fields)
    t = Table([label_row, value_row], colWidths=[col_w] * len(fields))
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0,0),(-1,-1), C_LIGHT_BLUE),
        ("TOPPADDING",    (0,0),(-1,-1), 3),
        ("BOTTOMPADDING", (0,0),(-1,-1), 3),
        ("LINEAFTER",     (0,0),(-2,-1), 0.5, colors.lightgrey),
    ]))
    return t


# ── Page template with header/footer ─────────────────────────────────────────

def _on_page(canvas, doc):
    canvas.saveState()
    # top rule
    canvas.setStrokeColor(C_DARK_BLUE)
    canvas.setLineWidth(1.5)
    canvas.line(MARGIN, PAGE_H - 10*mm, PAGE_W - MARGIN, PAGE_H - 10*mm)
    # footer
    canvas.setFont("Helvetica", 6.5)
    canvas.setFillColor(colors.grey)
    footer = (
        "DISCLAIMER: This report is for informational purposes only and does not constitute "
        "investment advice. Please consult your financial advisor before making any investment decisions."
    )
    canvas.drawCentredString(PAGE_W / 2, 8*mm, footer)
    canvas.setFont("Helvetica", 6.5)
    canvas.drawRightString(PAGE_W - MARGIN, 8*mm, f"Page {doc.page}")
    canvas.restoreState()


# ── Main generator ────────────────────────────────────────────────────────────

def generate_pdf(data: dict) -> bytes:
    """Build the equity research report PDF and return raw bytes."""
    buf = io.BytesIO()

    doc = BaseDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=1.8*cm, bottomMargin=1.8*cm,
        title=f"Equity Research – {data.get('company_name', '')}",
    )
    frame = Frame(MARGIN, 1.8*cm, CONTENT_W, PAGE_H - 3.6*cm, id="main")
    doc.addPageTemplates([PageTemplate(id="main", frames=[frame], onPage=_on_page)])

    story = []

    # 1. Header
    story.append(_header_table(data))
    story.append(Spacer(1, 4*mm))

    # 2. Stats bar
    story.append(_stats_bar(data))
    story.append(Spacer(1, 4*mm))

    # 3. Investment Highlights
    highlights = data.get("highlights") or []
    if highlights:
        story.append(_section_header("Investment Highlights", CONTENT_W))
        story.append(Spacer(1, 2*mm))
        for h in highlights:
            story.append(Paragraph(f"• {h}", S_BULLET))
        story.append(Spacer(1, 4*mm))

    # 4. Company Overview
    overview = data.get("company_overview", "")
    if overview:
        story.append(_section_header("Company Overview", CONTENT_W))
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(overview, S_BODY))
        story.append(Spacer(1, 4*mm))

    # 5. Financial Summary table
    fin_rows = data.get("financial_table") or []
    story.append(_section_header("Financial Summary", CONTENT_W))
    story.append(Spacer(1, 2*mm))
    if fin_rows:
        story.append(_financial_table(fin_rows))
    else:
        story.append(Paragraph("Financial data not available.", S_BODY))
    story.append(Spacer(1, 4*mm))

    # 6. Charts (Revenue/PAT  +  Margins) side by side
    img_rev = _chart_revenue_pat(fin_rows)
    img_marg = _chart_margins(fin_rows)
    if img_rev and img_marg:
        story.append(_section_header("Charts", CONTENT_W))
        story.append(Spacer(1, 2*mm))
        chart_tbl = Table([[img_rev, img_marg]],
                          colWidths=[CONTENT_W/2, CONTENT_W/2])
        chart_tbl.setStyle(TableStyle([
            ("VALIGN",   (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING", (0,0),(-1,-1), 4),
            ("RIGHTPADDING",(0,0),(-1,-1), 4),
        ]))
        story.append(chart_tbl)
        story.append(Spacer(1, 4*mm))

    # 7. Quarterly Results
    q_rows = data.get("quarterly_table") or []
    story.append(_section_header("Quarterly Results", CONTENT_W))
    story.append(Spacer(1, 2*mm))
    if q_rows:
        img_q = _chart_quarterly(q_rows)
        if img_q:
            qtbl = _quarterly_table(q_rows)
            side = Table([[qtbl, img_q]],
                         colWidths=[CONTENT_W * 0.42, CONTENT_W * 0.58])
            side.setStyle(TableStyle([
                ("VALIGN",      (0,0),(-1,-1), "TOP"),
                ("LEFTPADDING", (0,0),(-1,-1), 0),
                ("RIGHTPADDING",(0,0),(-1,-1), 4),
            ]))
            story.append(side)
        else:
            story.append(_quarterly_table(q_rows))
    else:
        story.append(Paragraph("Quarterly data not available.", S_BODY))
    story.append(Spacer(1, 4*mm))

    # 8. Investment Rationale + Recent Performance
    for key, label in [
        ("investment_rationale", "Investment Rationale"),
        ("recent_performance",   "Recent Performance"),
    ]:
        val = data.get(key, "")
        if val:
            story.append(_section_header(label, CONTENT_W))
            story.append(Spacer(1, 2*mm))
            story.append(Paragraph(val, S_BODY))
            story.append(Spacer(1, 4*mm))

    # 9. Risks + Outlook (two-column)
    risks   = data.get("risks", "")
    outlook = data.get("outlook", "")
    if risks or outlook:
        left_items  = []
        right_items = []
        if risks:
            left_items.append(_section_header("Key Risks", (CONTENT_W - 4*mm) / 2))
            left_items.append(Spacer(1, 2*mm))
            left_items.append(Paragraph(risks, S_BODY))
        if outlook:
            right_items.append(_section_header("Outlook & Recommendation", (CONTENT_W - 4*mm) / 2))
            right_items.append(Spacer(1, 2*mm))
            right_items.append(Paragraph(outlook, S_BODY))

        def _wrap(items):
            from reportlab.platypus import KeepInFrame
            return KeepInFrame((CONTENT_W - 4*mm) / 2, 999*cm, items, mode="shrink")

        two_col = Table([[_wrap(left_items), _wrap(right_items)]],
                        colWidths=[(CONTENT_W - 4*mm) / 2, (CONTENT_W - 4*mm) / 2])
        two_col.setStyle(TableStyle([
            ("VALIGN",      (0,0),(-1,-1), "TOP"),
            ("LEFTPADDING", (0,0),(-1,-1), 0),
            ("RIGHTPADDING",(0,0),(-1,-1), 0),
            ("COLPADDING",  (1,0),(1,-1),  4),
        ]))
        story.append(two_col)

    doc.build(story)
    return buf.getvalue()
