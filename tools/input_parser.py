"""
tools/input_parser.py
Parses all input types into clean plain text for the pipeline.
Supports: plain text, PDF (PyMuPDF), DOCX (python-docx), URL (requests + BS4)
"""

import fitz  # PyMuPDF
import docx
import requests
from bs4 import BeautifulSoup
from pathlib import Path


def parse_text(text: str) -> str:
    """Return plain text as-is after basic cleanup."""
    return text.strip()


def parse_pdf(file_bytes: bytes) -> str:
    """Extract text from PDF bytes using PyMuPDF."""
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages = []
    for page in doc:
        pages.append(page.get_text())
    doc.close()
    return "\n\n".join(pages).strip()


def parse_docx(file_bytes: bytes) -> str:
    """Extract text from DOCX bytes using python-docx."""
    import io
    doc = docx.Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs).strip()


def parse_url(url: str) -> str:
    """Scrape and extract main text content from a URL."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; SlideForgeBot/1.0)"}
    try:
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
    except Exception as e:
        raise ValueError(f"Failed to fetch URL '{url}': {e}")

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove scripts, styles, nav, footer
    for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
        tag.decompose()

    # Try to find main content area
    main = soup.find("main") or soup.find("article") or soup.find("body")
    text = main.get_text(separator="\n") if main else soup.get_text(separator="\n")

    # Clean up excessive whitespace
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return "\n".join(lines)[:8000]  # cap at 8k chars to avoid token overflow


def parse_input(
    input_type: str,
    text: str = None,
    file_bytes: bytes = None,
    url: str = None,
) -> str:
    """
    Unified entry point for all input types.
    input_type: 'text' | 'pdf' | 'docx' | 'url'
    Returns clean string content ready for the pipeline.
    """
    if input_type == "text":
        if not text:
            raise ValueError("text is required for input_type='text'")
        return parse_text(text)

    elif input_type == "pdf":
        if not file_bytes:
            raise ValueError("file_bytes is required for input_type='pdf'")
        return parse_pdf(file_bytes)

    elif input_type == "docx":
        if not file_bytes:
            raise ValueError("file_bytes is required for input_type='docx'")
        return parse_docx(file_bytes)

    elif input_type == "url":
        if not url:
            raise ValueError("url is required for input_type='url'")
        return parse_url(url)

    else:
        raise ValueError(f"Unknown input_type: '{input_type}'. Use text/pdf/docx/url.")
