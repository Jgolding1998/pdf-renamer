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
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / 'templates'))

# Regular expressions
CUST_REGEX = re.compile(r'Customer\s+No\s*[:#]?\s*([A-Za-z0-9]+)', re.IGNORECASE)
INV_REGEX = re.compile(r'Invoice\s+(?!Date|To)(\d+)', re.IGNORECASE)
ORDER_REGEX = re.compile(r'\b(?:SO|SV)\s*\d+\b', re.IGNORECASE)
SHIP_TO_REGEX = re.compile(r'Ship\s+To\s+Name[:\s]*([^\n\r]+)', re.IGNORECASE)

# Simple password required to access the uploader
SECRET_PASSWORD = "Justin is the best"

def extract_customer_number_from_pdf_bytes(data: bytes) -> Optional[str]:
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
    try:
        doc = fitz.open(stream=data, filetype='pdf')
    except Exception as exc:
        print(f"Failed to open PDF for sales order extraction: {exc}")
        return None, None

    full_text = ""
    for page in doc:
        try:
            full_text += page.get_text()
        except Exception:
            continue

    order_match = ORDER_REGEX.search(full_text)
    order_num = order_match.group(0).strip() if order_match else None
    ship_match = SHIP_TO_REGEX.search(full_text)
    ship_name = ship_match.group(1).strip() if ship_match else None
    return order_num, ship_name

def sanitize_name(name: str) -> str:
    return ''.join(c for c in name if c.isalnum() or c in ('-', '_'))

@app.get('/', response_class=HTMLResponse)
async def get_password(request: Request):
    return templates.TemplateResponse('password.html', {"request": request, "error": None})

@app.post('/login', response_class=HTMLResponse)
async def post_login(request: Request, password: str = Form(...)):
    if password == SECRET_PASSWORD:
        return templates.TemplateResponse('upload.html', {"request": request})
    else:
        error = ("Error: wrong password! If entered wrong again the computer will self-destruct. "
                 "Hint: Who is the best?")
        return templates.TemplateResponse('password.html', {"request": request, "error": error})

@app.get('/upload', response_class=HTMLResponse)
async def get_upload(request: Request):
    return templates.TemplateResponse('upload.html', {"request": request})

@app.post('/upload')
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            cust_num = extract_customer_number_from_pdf_bytes(data)
            if cust_num:
                new_name = f"CTI-{cust_num}.pdf"
            else:
                base_name = os.path.splitext(uploaded.filename or 'invoice')[0]
                new_name = f"CTI-{sanitize_name(base_name)}.pdf"
            zf.writestr(new_name, data)

    memory_file.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    zip_name = f"renamed_invoices_{timestamp}.zip"
    headers = {'Content-Disposition': f'attachment; filename="{zip_name}"'}
    return StreamingResponse(memory_file, media_type='application/x-zip-compressed', headers=headers)

@app.post('/upload_invoice')
async def upload_files_invoice(request: Request, files: List[UploadFile] = File(...)):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            inv_num = extract_invoice_number_from_pdf_bytes(data)
            if inv_num:
                new_name = f"CTI-{inv_num}.pdf"
            else:
                base_name = os.path.splitext(uploaded.filename or 'invoice')[0]
                new_name = f"CTI-{sanitize_name(base_name)}.pdf"
            zf.writestr(new_name, data)

    memory_file.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    zip_name = f"renamed_invoices_{timestamp}.zip"
    headers = {'Content-Disposition': f'attachment; filename="{zip_name}"'}
    return StreamingResponse(memory_file, media_type='application/x-zip-compressed', headers=headers)

@app.post('/upload_cust_invoice')
async def upload_cust_invoice_files(request: Request, files: List[UploadFile] = File(...)):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            cust_num = extract_customer_number_from_pdf_bytes(data)
            inv_num = extract_invoice_number_from_pdf_bytes(data)
            if cust_num and inv_num:
                new_name = f"CTI-{cust_num}-{inv_num}.pdf"
            elif cust_num:
                new_name = f"CTI-{cust_num}.pdf"
            elif inv_num:
                new_name = f"CTI-{inv_num}.pdf"
            else:
                base_name = os.path.splitext(uploaded.filename or 'invoice')[0]
                new_name = f"CTI-{sanitize_name(base_name)}.pdf"
            zf.writestr(new_name, data)

    memory_file.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    zip_name = f"renamed_invoices_{timestamp}.zip"
    headers = {'Content-Disposition': f'attachment; filename="{zip_name}"'}
    return StreamingResponse(memory_file, media_type='application/x-zip-compressed', headers=headers)

@app.post('/upload_salesorder')
async def upload_salesorder_files(request: Request, files: List[UploadFile] = File(...)):
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            data = await uploaded.read()
            order_num, ship_name = extract_sales_order_details_from_pdf_bytes(data)
            if order_num and ship_name:
                safe_ship = sanitize_name(ship_name.replace(' ', '_'))
                new_name = f"CTI Sales Order {order_num} {safe_ship}.pdf"
            elif order_num:
                new_name = f"CTI Sales Order {order_num}.pdf"
            else:
                base_name = os.path.splitext(uploaded.filename or 'salesorder')[0]
                new_name = f"CTI Sales Order {sanitize_name(base_name)}.pdf"
            zf.writestr(new_name, data)

    memory_file.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    zip_name = f"renamed_salesorders_{timestamp}.zip"
    headers = {'Content-Disposition': f'attachment; filename="{zip_name}"'}
    return StreamingResponse(memory_file, media_type='application/x-zip-compressed', headers=headers)

# Mount static folder
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')
