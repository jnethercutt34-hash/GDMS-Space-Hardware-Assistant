import io
import pdfplumber


def extract_text_from_pdf(pdf_bytes: bytes) -> dict:
    """Extract text from PDF bytes.

    Returns a dict with:
        page_count  - total number of pages
        text        - full concatenated text (pages joined by double newline)
        pages       - list of per-page text strings
    """
    text_pages = []

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        page_count = len(pdf.pages)
        for page in pdf.pages:
            page_text = page.extract_text() or ""
            text_pages.append(page_text)

    return {
        "page_count": page_count,
        "text": "\n\n".join(text_pages),
        "pages": text_pages,
    }
