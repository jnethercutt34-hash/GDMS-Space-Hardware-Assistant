"""Quick test: extract text from the TPS7H1111 PDF using PyMuPDF, then run LLM extraction."""
import sys
import os
import logging
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

import json

LOG_PATH = os.path.join(os.path.dirname(__file__), "test_output.log")

# Set up logging to capture ai_extractor debug info
logging.basicConfig(
    level=logging.DEBUG,
    format="%(name)s %(levelname)s: %(message)s",
    handlers=[logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")]
)
logger = logging.getLogger(__name__)

logger.info("Step 1: Extracting PDF text...")
from services.pdf_extractor import extract_text_from_pdf

PDF_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "tps7h1111-sep.pdf")
with open(PDF_PATH, "rb") as f:
    result = extract_text_from_pdf(f.read())

logger.info(f"Pages: {result['page_count']}, Text: {len(result['text'])} chars")

logger.info("Step 2: Sending to LLM...")
try:
    from services.ai_extractor import extract_components_from_text
    rows, warnings = extract_components_from_text(result["text"])
    logger.info(f"Step 3: Extracted {len(rows)} components:")
    for r in rows:
        d = r.model_dump()
        logger.info(json.dumps(d, indent=2))
    logger.info(f"Warnings: {warnings}")
except Exception as e:
    import traceback
    logger.error(f"{type(e).__name__}: {e}")
    logger.error(traceback.format_exc())

logger.info("DONE")
