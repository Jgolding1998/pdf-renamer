import io
import os
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import List, Optional

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

# Regular expression for extracting customer number
CUST_REGEX = re.compile(r'Customer\s+No\s*[:#]?\s*([A-Za-z0-9]+)', re.IGNORECASE)

# Simple password required to access the uploader
SECRET_PASSWORD = "Justin is the best"


def extract_customer_number_from_pdf_bytes(data: bytes) -> Optional[str]:
    """
    Given PDF data in bytes, extract the customer number using PyMuPDF.
    Returns the customer number string if found, otherwise None.
    """
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


def sanitize_name(name: str) -> str:
    """
    Sanitize string to contain only alphanumeric, dash and underscore.
    """
    return ''.join(c for c in name if c.isalnum() or c in ('-', '_'))


@app.get('/', response_class=HTMLResponse)
async def get_password(request: Request):
    """
    Display the password entry page.
    """
    return templates.TemplateResponse('password.html', {"request": request, "error": None})


@app.post('/login', response_class=HTMLResponse)
async def post_login(request: Request, password: str = Form(...)):
    """
    Validate the password and render the upload page if correct.
    """
    if password == SECRET_PASSWORD:
        # Render the upload form with a funny message
        return templates.TemplateResponse('upload.html', {"request": request})
    else:
        # Provide a humorous error message when the password is wrong
        error = ("Error: wrong password! If entered wrong again the computer will self-destruct. "
                 "Hint: Who is the best?")
        return templates.TemplateResponse('password.html', {"request": request, "error": error})


@app.get('/upload', response_class=HTMLResponse)
async def get_upload(request: Request):
    """
    Render upload form. This route should not be accessed directly without password,
    but is available for convenience.
    """
    return templates.TemplateResponse('upload.html', {"request": request})


@app.post('/upload')
async def upload_files(request: Request, files: List[UploadFile] = File(...)):
    """
    Handle uploaded PDF files, extract customer numbers, and return a zip file
    containing renamed PDFs.
    """
    # Prepare in-memory zip file
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, mode='w', compression=zipfile.ZIP_DEFLATED) as zf:
        for uploaded in files:
            # Read bytes
            data = await uploaded.read()
            # Extract number
            cust_num = extract_customer_number_from_pdf_bytes(data)
            if cust_num:
                new_name = f"CTI-{cust_num}.pdf"
            else:
                # fallback: use original filename sans extension sanitized
                base_name = os.path.splitext(uploaded.filename or 'invoice')[0]
                new_name = f"CTI-{sanitize_name(base_name)}.pdf"
            # Write to zip
            zf.writestr(new_name, data)

    memory_file.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    zip_name = f"renamed_invoices_{timestamp}.zip"
    headers = {
        'Content-Disposition': f'attachment; filename="{zip_name}"'
    }
    return StreamingResponse(memory_file, media_type='application/x-zip-compressed', headers=headers)


# Mount static folder (if needed)
app.mount('/static', StaticFiles(directory=str(BASE_DIR / 'static')), name='static')