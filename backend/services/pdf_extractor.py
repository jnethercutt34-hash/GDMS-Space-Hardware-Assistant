"""PDF text extraction — uses PyMuPDF (fitz) for reliable, fast extraction.

Previously used pdfplumber, but it hangs on certain complex datasheets
(e.g. TI TPS7H1111-SEP with vector graphics). PyMuPDF handles these
reliably and is significantly faster.
"""
import io
import fitz  # PyMuPDF


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """Extract text from PDF bytes.

    Returns a dict with:
        page_count  - total number of pages
        text        - full concatenated text (pages joined by double newline)
        pages       - list of per-page text strings
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_count = doc.page_count
    text_pages = []
    for i in range(page_count):
        page_text = doc[i].get_text() or ""
        text_pages.append(page_text)
    doc.close()

    return {
        "page_count": page_count,
        "text": "\n\n".join(text_pages),
        "pages": text_pages,
    }
