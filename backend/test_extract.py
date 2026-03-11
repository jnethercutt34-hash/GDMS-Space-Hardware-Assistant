from dotenv import load_dotenv
load_dotenv()

from services.pdf_extractor import extract_text_from_pdf
from services.ai_extractor import extract_components_from_text

with open('../docs/tps7h1111-sep.pdf', 'rb') as f:
    result = extract_text_from_pdf(f.read())

print(f'Pages: {result["page_count"]}', flush=True)
print(f'Text length: {len(result["text"])}', flush=True)
print(f'Sending first 14000 chars to LLM...', flush=True)

rows, warnings = extract_components_from_text(result['text'])
print(f'\nExtracted {len(rows)} components:', flush=True)
for r in rows:
    print(r.model_dump(), flush=True)
print(f'\nWarnings: {warnings}', flush=True)
