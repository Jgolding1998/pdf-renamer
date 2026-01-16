import io
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import fitz  # PyMuPDF
from fastapi import FastAPI, File, UploadFile, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles

# Initialize FastAPI app
app = FastAPI()

# Set up template directory
templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(templates_dir))

# Regular expressions for customer and invoice numbers
CUST_REGEX = re.compile(r"Customer\s*(?:No\s*[:#]?\s*|Number\s*[:\s]*)\s*([A-Za-z0-9\-]+)", re.IGNORECASE)
INV_REGEX = re.compile(r"Invoice\s*(?:No\s*[:#]?\s*|Number\s*[:\s]*)\s*([A-Za-z0-9\-]+)", re.IGNORECASE)
# Fallback regex to find SO or SV style order numbers anywhere in the text
ORDER_FALLBACK_REGEX = re.compile(r"\b(?:SO|SV)[A-Za-z0-9]+\b", re.IGNORECASE)

# Simple password required to access the uploader
SECRET_PASSWORD = "Justin is the best"

def extract_customer_number_from_pdf_bytes(data: bytes) -> Optional[str]:
    """Extract a customer number from PDF bytes."""
    try:
        doc = fitz.open(stream=data, filetype='pdf')
    except Exception as exc:
        print(f"Failed to open PDF: {exc}")
        return None
    full_text = ""
    for page in doc:
        try:
            full_text += page.get_text()
        except Exception:
            continue
    match = CUST_REGEX.search(full_text)
    return match.group(1).strip() if match else None

def extract_invoice_number_from_pdf_bytes(data: bytes) -> Optional[str]:
    """Extract an invoice number from PDF bytes."""
    try:
        doc = fitz.open(stream=data, filetype='pdf')
    except Exception as exc:
        print(f"Failed to open PDF for invoice extraction: {exc}")
        return None
    full_text = ""
    for page in doc:
        try:
            full_text += page.get_text()
        except Exception:
            continue
    match = INV_REGEX.search(full_text)
    return match.group(1).strip() if match else None

def extract_sales_order_details_from_pdf_bytes(data: bytes) -> Tuple[Optional[str], Optional[str]]:
    """Extract sales order number and ship-to name from PDF bytes."""
    order_num: Optional[str] = None
    ship_name: Optional[str] = None
    try:
        doc = fitz.open(stream=data, filetype='pdf')
    except Exception as exc:
        print(f"Failed to open PDF for sales order extraction: {exc}")
        return None, None
    lines: List[str] = []
    for page in doc:
        try:
            text = page.get_text()
            if text:
                lines.extend(text.splitlines())
        except Exception:
            continue
    for idx, line in enumerate(lines):
        if order_num is None:
            m = re.search(r"Order\s*Number\s*[:\s]*([A-Za-z0-9\-]+)", line, re.IGNORECASE)
            if not m:
                m = re.search(r"Sales\s*Order\s*[:\s]*([A-Za-z0-9\-]+)", line, re.IGNORECASE)
            if not m:
                m = re.search(r"\b(?:SO|SV)[A-Za-z0-9]+\b", line, re.IGNORECASE)
                if m:
                    order_num = m.group(0).strip()
            else:
                order_num = m.group(1).strip()
        if ship_name is None:
            ship_match = re.match(r"\s*Ship\s*To\b[\s:]*", line, re.IGNORECASE)
            if ship_match:
                after = line[ship_match.end():].strip()
                candidate = after
                if not candidate:
                    # Use the next non-empty line as candidate
                    for j in range(idx + 1, len(lines)):
                        next_line = lines[j].strip()
                        if next_line:
                            candidate = next_line
                            break
                if candidate:
                    # Remove address information starting with digits
                    candidate = re.sub(r"\s*\d.*", "", candidate).strip()
                    ship_name = candidate
        if order_num is not None and ship_name is not None:
            break
    # Fallback search for order number across entire document
    if order_num is None:
        full_text = "\n".join(lines)
        m = ORDER_FALLBACK_REGEX.search(full_text)
        if m:
            order_num = m.group(0).strip()
    return order_num, ship_name

def sanitize_name(name: str) -> str:
    """Sanitize a filename by allowing only alphanumeric characters, dash and underscore."""
    return ''.join(c for c in name if c.isalnum() or c in ('-', '_'))

@app.get("/", response_class=HTMLResponse)
async def get_password(request: Request):
    """Render the password page."""
    return templates.TemplateResponse("password.html", {"request": request, "error": None})

@app.post("/login", response_class=HTMLResponse)
async def post_login(request: Request, password: str = Form(...)):
    """Handle password submission and render the upload page if correct."""
    if password == SECRET_PASSWORD:
        return templates.TemplateResponse("upload.html", {"request": request})
    else:
        error = "Error: wrong password! If entered wrong again the computer will self-destruct. Hint: Who is the best?"
        return templates.TemplateResponse("password.html", {"request": request, "error": error})

@app.post("/upload")
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    """Handle uploads for customer-number-based renaming."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            cust_num = extract_customer_number_from_pdf_bytes(data)
            if cust_num:
                new_name = f"CTI-{cust_num}.pdf"
            else:
                base_name = Path(uploaded.filename or "file").stem
                new_name = sanitize_name(base_name) + ".pdf"
            zf.writestr(new_name, data)
    memory_file.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=renamed_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"}
    return StreamingResponse(memory_file, media_type="application/x-zip-compressed", headers=headers)

@app.post("/upload_invoice")
async def upload_files_invoice(request: Request, files: List[UploadFile] = File(...)):
    """Handle uploads for invoice-number-based renaming."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            inv_num = extract_invoice_number_from_pdf_bytes(data)
            if inv_num:
                new_name = f"CTI-{inv_num}.pdf"
            else:
                base_name = Path(uploaded.filename or "file").stem
                new_name = sanitize_name(base_name) + ".pdf"
            zf.writestr(new_name, data)
    memory_file.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=renamed_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"}
    return StreamingResponse(memory_file, media_type="application/x-zip-compressed", headers=headers)

@app.post("/upload_salesorder")
async def upload_salesorder_files(request: Request, files: List[UploadFile] = File(...)):
    """Handle uploads for sales-order-based renaming."""
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            order_num, ship_name = extract_sales_order_details_from_pdf_bytes(data)
            if order_num and ship_name:
                proposed = f"CTI Sales Order {order_num} {ship_name}.pdf"
            elif order_num:
                proposed = f"CTI Sales Order {order_num}.pdf"
            elif ship_name:
                proposed = f"CTI Sales Order {ship_name}.pdf"
            else:
                base_name = Path(uploaded.filename or "file").stem
                proposed = sanitize_name(base_name) + ".pdf"
            safe_name = sanitize_name(proposed)
            zf.writestr(safe_name, data)
    memory_file.seek(0)
    headers = {"Content-Disposition": f"attachment; filename=renamed_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip"}
    return StreamingResponse(memory_file, media_type="application/x-zip-compressed", headers=headers)

# Mount static directory for CSS or JS assets if needed
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

