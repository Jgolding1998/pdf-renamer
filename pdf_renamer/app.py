"""
Flask application for renaming PDF files based on values extracted from
their contents. This app provides four separate upload endpoints for
different renaming schemes: customer number, invoice number,
customer and invoice combined, and sales order details. Uploaded
PDFs are processed, renamed, zipped and returned to the user for
download. Drag-and-drop upload functionality is handled on the
front-end by JavaScript.
"""

import os
import re
import zipfile
from io import BytesIO
from typing import List, Tuple, Optional

from flask import Flask, render_template, request, send_file
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader

# Create Flask application
app = Flask(__name__)

# Directory for temporary uploads
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def extract_customer_number(file_path: str) -> Optional[str]:
    """Extract a customer number from the PDF.

    Looks for patterns like 'Customer Number: XXXXX' and returns
    the matched value. Returns None if nothing is found.
    """
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            text = page.extract_text() or ""
            match = re.search(r"Customer\s*Number\s*[:\s]*([A-Za-z0-9\-]+)", text)
            if match:
                return match.group(1).strip()
        return None
    except Exception as exc:
        print(f"Error extracting customer number from {file_path}: {exc}")
        return None

def extract_invoice_number(file_path: str) -> Optional[str]:
    """Extract an invoice number from the PDF.

    Searches for 'Invoice Number: XXXXX' patterns. Returns the
    invoice value or None.
    """
    try:
        reader = PdfReader(file_path)
        for page in reader.pages:
            text = page.extract_text() or ""
            match = re.search(r"Invoice\s*Number\s*[:\s]*([A-Za-z0-9\-]+)", text)
            if match:
                return match.group(1).strip()
        return None
    except Exception as exc:
        print(f"Error extracting invoice number from {file_path}: {exc}")
        return None

def extract_sales_order_details(file_path: str) -> Tuple[Optional[str], Optional[str]]:
    """Extract the sales order number and ship-to name from the PDF.

    Attempts multiple patterns to find a sales order identifier (often
    starting with 'SV' or labelled 'Sales Order') and the ship-to
    recipient (labelled 'Ship to' or 'Ship to Name'). If either
    component is missing, returns None for that value.
    """
    order_number = None
    ship_name = None
    try:
        reader = PdfReader(file_path)
        text = "".join([page.extract_text() or "" for page in reader.pages])
        # Find order number: look for 'Sales Order: XYZ' or pattern like SV123456
        order_match = re.search(r"Sales\s*Order\s*[:\s]*([A-Za-z0-9\-]+)", text, re.IGNORECASE)
        if not order_match:
            order_match = re.search(r"\bSV[0-9A-Za-z]+\b", text)
        if order_match:
            order_number = order_match.group(1).strip()
        # Find ship-to name: look for 'Ship to:' or 'Ship to Name:' followed by text
        ship_match = re.search(r"Ship\s*to(?:\s*Name)?\s*[:\s]*([A-Za-z0-9 ,.'\-]+)", text, re.IGNORECASE)
        if ship_match:
            ship_name = ship_match.group(1).strip()
    except Exception as exc:
        print(f"Error extracting sales order details from {file_path}: {exc}")
    return order_number, ship_name

def zip_files(file_tuples: List[Tuple[str, str]]) -> BytesIO:
    """Create an in-memory ZIP archive from a list of (path, arcname) tuples.

    Each tuple should contain the original file path and the desired
    archive name. Returns a BytesIO object positioned at the
    beginning for streaming via Flask.
    """
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for path, arcname in file_tuples:
            zipf.write(path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

@app.route('/')
def index():
    """Render the upload page."""
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload():
    """Handle uploads for customer-number-based renaming."""
    uploaded_files = request.files.getlist('files')
    renamed: List[Tuple[str, str]] = []
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(temp_path)
        customer_number = extract_customer_number(temp_path)
        new_name = f"CTI-{customer_number}.pdf" if customer_number else filename
        renamed.append((temp_path, new_name))
    zip_buffer = zip_files(renamed)
    return send_file(zip_buffer, as_attachment=True, download_name='renamed.zip', mimetype='application/zip')

@app.route('/upload_invoice', methods=['POST'])
def upload_invoice():
    """Handle uploads for invoice-number-based renaming."""
    uploaded_files = request.files.getlist('files')
    renamed: List[Tuple[str, str]] = []
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(temp_path)
        invoice_number = extract_invoice_number(temp_path)
        new_name = f"CTI-{invoice_number}.pdf" if invoice_number else filename
        renamed.append((temp_path, new_name))
    zip_buffer = zip_files(renamed)
    return send_file(zip_buffer, as_attachment=True, download_name='renamed.zip', mimetype='application/zip')

@app.route('/upload_cust_invoice', methods=['POST'])
def upload_cust_invoice():
    """Handle uploads for combined customer and invoice renaming.

    Each PDF is renamed using both the customer number and invoice
    number if available, producing names like 'CTI-12345-67890.pdf'.
    If only one of the values is found, the available one is used.
    """
    uploaded_files = request.files.getlist('files')
    renamed: List[Tuple[str, str]] = []
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(temp_path)
        customer_number = extract_customer_number(temp_path)
        invoice_number = extract_invoice_number(temp_path)
        if customer_number and invoice_number:
            new_name = f"CTI-{customer_number}-{invoice_number}.pdf"
        elif customer_number:
            new_name = f"CTI-{customer_number}.pdf"
        elif invoice_number:
            new_name = f"CTI-{invoice_number}.pdf"
        else:
            new_name = filename
        renamed.append((temp_path, new_name))
    zip_buffer = zip_files(renamed)
    return send_file(zip_buffer, as_attachment=True, download_name='renamed.zip', mimetype='application/zip')

@app.route('/upload_salesorder', methods=['POST'])
def upload_salesorder():
    """Handle uploads for sales-order-based renaming.

    PDF files are renamed according to the pattern:
    'CTI Sales Order <order-number> <ship-to-name>.pdf'. If either
    component is missing, the available information is used. If none
    is found, the original filename is retained.
    """
    uploaded_files = request.files.getlist('files')
    renamed: List[Tuple[str, str]] = []
    for file in uploaded_files:
        filename = secure_filename(file.filename)
        temp_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(temp_path)
        order_number, ship_name = extract_sales_order_details(temp_path)
        if order_number and ship_name:
            new_name = f"CTI Sales Order {order_number} {ship_name}.pdf"
        elif order_number:
            new_name = f"CTI Sales Order {order_number}.pdf"
        elif ship_name:
            new_name = f"CTI Sales Order {ship_name}.pdf"
        else:
            new_name = filename
        renamed.append((temp_path, new_name))
    zip_buffer = zip_files(renamed)
    return send_file(zip_buffer, as_attachment=True, download_name='renamed.zip', mimetype='application/zip')

if __name__ == '__main__':
    # Enable debug for development convenience
    app.run(host='0.0.0.0', port=5000, debug=True)
