"""
generate_examples.py
Generates two sample equity research PDFs from the provided test documents.
Run from the backend/ directory:
    python generate_examples.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from extractor import extract_data
from pdf_generator import generate_pdf

EXAMPLES = [
    {
        "input":  "../sample_inputs/reliance_industries.txt",
        "output": "../sample_outputs/Reliance_Industries_equity_report.pdf",
        "company": "Reliance Industries Limited",
    },
    {
        "input":  "../sample_inputs/infosys_financials.csv",
        "output": "../sample_outputs/Infosys_equity_report.pdf",
        "company": "Infosys Limited",
    },
]

os.makedirs(os.path.join(os.path.dirname(__file__), "../sample_outputs"), exist_ok=True)

for ex in EXAMPLES:
    base = os.path.dirname(__file__)
    in_path  = os.path.normpath(os.path.join(base, ex["input"]))
    out_path = os.path.normpath(os.path.join(base, ex["output"]))

    print(f"\n→ Processing: {ex['company']}")
    with open(in_path, "rb") as f:
        file_bytes = f.read()

    data = extract_data(file_bytes, os.path.basename(in_path), ex["company"])
    data["company_name"] = ex["company"]          # ensure name is set

    pdf_bytes = generate_pdf(data)
    with open(out_path, "wb") as f:
        f.write(pdf_bytes)
    print(f"  ✓ Saved: {out_path}  ({len(pdf_bytes)//1024} KB)")

print("\nAll example PDFs generated successfully.")
