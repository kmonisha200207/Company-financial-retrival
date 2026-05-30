"""
main.py – FastAPI backend for the Equity Report Generator.

Endpoints:
  POST /api/generate   – upload context doc → returns PDF bytes
  GET  /api/health     – liveness check
"""

from __future__ import annotations

import traceback
from typing import Annotated

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse

from extractor import extract_data
from pdf_generator import generate_pdf

app = FastAPI(title="Equity Report Generator", version="1.0.0")

# Allow requests from the React dev server (Vite default: 5173)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/generate")
async def generate_report(
    company_name: Annotated[str, Form()],
    file: Annotated[UploadFile, File()],
):
    """
    Accept a context document (PDF / TXT / CSV) and return a filled PDF report.
    """
    allowed_types = {
        "application/pdf",
        "text/plain",
        "text/csv",
        "application/csv",
        "application/vnd.ms-excel",
        "application/octet-stream",  # generic fallback
    }
    content_type = file.content_type or "application/octet-stream"
    filename = file.filename or "upload.txt"

    # Validate by extension as well (content_type can be unreliable)
    ext = filename.rsplit(".", 1)[-1].lower()
    if ext not in {"pdf", "txt", "csv", "tsv"}:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type '.{ext}'. Accepted: pdf, txt, csv.",
        )

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        extracted = extract_data(file_bytes, filename, company_name.strip())
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Extraction error: {exc}") from exc

    # Ensure company_name from form overrides extracted value
    if company_name.strip():
        extracted["company_name"] = company_name.strip()

    try:
        pdf_bytes = generate_pdf(extracted)
    except Exception as exc:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"PDF generation error: {exc}") from exc

    safe_name = "".join(c if c.isalnum() else "_" for c in company_name[:40])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_equity_report.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )
