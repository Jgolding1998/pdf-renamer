# PDF Renamer Web App

This repository contains a small web application that lets you upload PDF invoices, extract the customer number ("Customer No") from each PDF and rename the files using the format CTI-<CustomerNumber>.pdf. It then returns the renamed files as a ZIP archive. To access the upload form, visitors must enter a password.

## Password

On the home page you’ll be prompted to enter a password. The current password is:

Justin is the best

After entering the password, you’ll see the upload form along with a light‑hearted message reminding everyone how great Justin is.

## Features

- Upload one or multiple PDF files.
- Extracts the customer number using a simple regular expression.
- Renames files to CTI-<CustomerNumber>.pdf (falls back to original base name if none is found).
- Returns a ZIP archive with all renamed files.
- Password‑protected homepage.

## Running locally

1. Install dependencies (fastapi, uvicorn, pymupdf, python-multipart, jinja2).
2. Start the server using: uvicorn pdf_renamer.app:app --host 0.0.0.0 --port 8000
3. Open your browser to http://localhost:8000.

## Deployment

This app is designed to run on a Python‑capable host (such as Render.com or a similar platform that supports FastAPI). Static‑only hosts like GitHub Pages or Netlify will not run the backend code.
