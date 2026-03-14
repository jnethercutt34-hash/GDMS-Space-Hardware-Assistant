# Security Note: LLM Prompt Injection Risk

## Overview

The GDMS Space Hardware Assistant sends user-provided content (PDF text, BOM data,
schematic netlists) directly into LLM prompts for AI-powered extraction and analysis.
This creates a **prompt injection** attack surface: a malicious PDF could contain
text crafted to manipulate the LLM into producing incorrect output.

## Attack Surface

| Module | User Input → LLM | Risk |
|--------|-------------------|------|
| Component Librarian | PDF datasheet text → extraction prompt | Fabricated part specs |
| FPGA Risk Assessor | Pinout CSV + AI analysis prompt | Wrong risk classification |
| Constraint Extractor | PDF text → constraint extraction prompt | Missing/fabricated constraints |
| Block Diagram Builder | PDF text → architecture extraction prompt | Incorrect block diagram |
| COM Channel Analysis | User parameters → analysis prompt | Wrong pass/fail result |

## Current Defenses

1. **Pydantic Output Validation**: All AI responses are parsed through strict Pydantic
   models. The LLM cannot return arbitrary data — it must conform to the expected schema
   (field names, types, value ranges). This is the primary defense.

2. **Structured JSON Prompts**: Prompts request JSON output with specific field names.
   Even if the LLM is manipulated, the Pydantic model rejects non-conforming output.

3. **Human-in-the-Loop**: The Component Librarian uses a staging workflow — extracted
   data is shown to the engineer for review before being accepted into the library.
   Engineers are expected to verify critical specs against the original datasheet.

4. **No Code Execution**: LLM output is never executed as code. It is always treated
   as structured data.

## Limitations

- Pydantic validates **structure**, not **semantic correctness**. A prompt injection
  could cause the LLM to return `"Radiation_TID": "1000 krad"` when the real spec
  is 100 krad. The Pydantic model would accept this because it's a valid string.

- The human-in-the-loop review is only present in the Librarian module. Other modules
  (COM analysis, DRC) present AI results directly.

## Recommendations

1. **Do not use this tool as the sole source of truth** for flight hardware decisions.
   Always verify critical specifications (radiation, thermal, electrical) against
   original datasheets.

2. **Treat AI-extracted data as draft** — suitable for early design trade studies,
   not for CDR-level documentation without human verification.

3. **Future improvement**: Add confidence scores to AI extraction results and flag
   low-confidence values for mandatory human review.

4. **Future improvement**: Implement output sanity checks (e.g., TID values must be
   in a reasonable range for the part family, pin counts must match known packages).

## References

- [OWASP LLM Top 10 — Prompt Injection](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [Simon Willison — Prompt Injection Explained](https://simonwillison.net/2023/Apr/14/worst-that-can-happen/)
