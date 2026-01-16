import io
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

# =========================
# APP SETUP
# =========================

app = FastAPI()

BASE_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))

SECRET_PASSWORD = "Justin is the best"

# =========================
# HELPERS
# =========================

def sanitize_filename(name: str) -> str:
    """
    Remove only characters illegal in filenames.
    KEEP spaces, dashes, and dots.
    """
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


# =========================
# CUSTOMER / INVOICE
# =========================

CUST_REGEX = re.compile(
    r"Customer\s*(?:No|Number)?\s*[:#]?\s*([A-Za-z0-9\-]+)",
    re.IGNORECASE,
)

INV_REGEX = re.compile(
    r"Invoice\s*(?:No|Number)?\s*[:#]?\s*([A-Za-z0-9\-]+)",
    re.IGNORECASE,
)


def extract_customer_number(pdf_bytes: bytes) -> Optional[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    m = CUST_REGEX.search(text)
    return m.group(1).strip() if m else None


def extract_invoice_number(pdf_bytes: bytes) -> Optional[str]:
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "".join(page.get_text() for page in doc)
    m = INV_REGEX.search(text)
    return m.group(1).strip() if m else None


# =========================
# SALES ORDER EXTRACTION
# =========================

def extract_sales_order_info(pdf_bytes: bytes) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract:
    - Order Number (SV / SO)
    - Ship To name (FIRST LINE ONLY)
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    lines: List[str] = []

    for page in doc:
        lines.extend(page.get_text().splitlines())

    full_text = "\n".join(lines)

    # ---- ORDER NUMBER ----
    order_number = None

    for line in lines:
        if "Order Number" in line:
            parts = line.split(":")
            if len(parts) > 1:
                order_number = parts[1].strip()
                break

    if not order_number:
        m = re.search(r"\bSV\d{6,}\b", full_text)
        if m:
            order_number = m.group(0)

    # ---- SHIP TO (FIRST LINE AFTER HEADER) ----
    ship_to = None
    for i, line in enumerate(lines):
        if line.strip().lower().startswith("ship to"):
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    ship_to = lines[j].strip()
                    break
            break

    return order_number, ship_to


# =========================
# ROUTES
# =========================

@app.get("/", response_class=HTMLResponse)
async def password_page(request: Request):
    return templates.TemplateResponse("password.html", {"request": request})


@app.post("/login", response_class=HTMLResponse)
async def login(request: Request, password: str = Form(...)):
    if password == SECRET_PASSWORD:
        return templates.TemplateResponse("upload.html", {"request": request})
    return templates.TemplateResponse(
        "password.html",
        {
            "request": request,
            "error": "Wrong password. Hint: Who is the best?",
        },
    )


# =========================
# CUSTOMER NUMBER UPLOAD
# =========================

@app.post("/upload")
async def upload_customer(files: List[UploadFile] = File(...)):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            data = await f.read()
            cust = extract_customer_number(data)
            name = f"CTI-{cust}.pdf" if cust else f.filename
            zf.writestr(sanitize_filename(name), data)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=renamed_customers.zip"},
    )


# =========================
# INVOICE NUMBER UPLOAD
# =========================

@app.post("/upload_invoice")
async def upload_invoice(files: List[UploadFile] = File(...)):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            data = await f.read()
            inv = extract_invoice_number(data)
            name = f"CTI-{inv}.pdf" if inv else f.filename
            zf.writestr(sanitize_filename(name), data)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=renamed_invoices.zip"},
    )


# =========================
# SALES ORDER UPLOAD (FIXED)
# =========================

@app.post("/upload_salesorder")
async def upload_salesorder(files: List[UploadFile] = File(...)):
    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            data = await f.read()

            order_num, ship_to = extract_sales_order_info(data)

            if order_num and ship_to:
                filename = f"CTI Sales Order {order_num} {ship_to}.pdf"
            elif order_num:
                filename = f"CTI Sales Order {order_num}.pdf"
            else:
                filename = f.filename or "CTI Sales Order.pdf"

            zf.writestr(sanitize_filename(filename), data)

    zip_buffer.seek(0)
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=renamed_salesorders.zip"},
    )


# =========================
# STATIC FILES
# =========================

static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")
