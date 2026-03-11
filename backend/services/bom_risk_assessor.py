"""AI-assisted risk assessment for BOM parts (Phase 6).

For parts not in the library (or with incomplete data), queries the LLM
to assess lifecycle status, radiation tolerance, and suggest alternates.
"""
import json
from typing import List

from pydantic import ValidationError

from models.bom import (
    AIBatchRiskAssessment,
    AIRiskAssessment,
    BOMLineItem,
    LifecycleStatus,
    RadiationGrade,
)
from services.ai_client import get_client, get_model

_MAX_PARTS_PER_CALL = 20


def _build_system_prompt() -> str:
    schema = AIBatchRiskAssessment.model_json_schema()
    return f"""You are an aerospace electronics parts analyst specialising in space-grade and defence components.

You will receive a list of electronic parts from a Bill of Materials (BOM). For each part, assess:

1. **lifecycle_status**: One of Active, NRND, Obsolete, Unknown. Base this on your knowledge of the manufacturer and part family.
2. **radiation_grade**: One of Commercial, MIL, RadTolerant, RadHard, Unknown. Infer from part number suffixes, manufacturer radiation-hardening programs, and known rad-test data.
3. **risk_flags**: List any concerns — single-source, long lead times, known DMSMS alerts, export control (ITAR/EAR), or thermal/voltage derating issues.
4. **alt_parts**: Suggest 0–3 alternate parts (part_number, manufacturer, notes) that are form/fit/function compatible and preferably higher radiation grade or better lifecycle status.
5. **assessment**: One sentence summarising the overall risk posture of this part for a space application.

Return a JSON object conforming to this schema:

{json.dumps(schema, indent=2)}

The "assessments" array MUST have the same length as the input parts list, in the same order.
Return ONLY the JSON object. No markdown, no prose."""


def assess_risks_batch(items: List[BOMLineItem]) -> List[AIRiskAssessment]:
    """Send a batch of BOM line items to the LLM for risk assessment.

    Returns one AIRiskAssessment per input item (same order).
    """
    if not items:
        return []

    client = get_client()
    model = get_model()

    # Chunk if necessary
    all_assessments: List[AIRiskAssessment] = []
    for start in range(0, len(items), _MAX_PARTS_PER_CALL):
        chunk = items[start : start + _MAX_PARTS_PER_CALL]
        parts_text = "\n".join(
            f"{i+1}. Part: {item.part_number} | Mfr: {item.manufacturer} | Desc: {item.description}"
            for i, item in enumerate(chunk)
        )

        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            temperature=0.0,
            messages=[
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": f"Assess the following {len(chunk)} parts:\n\n{parts_text}",
                },
            ],
        )

        raw = response.choices[0].message.content
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            # Fall back to unknowns
            all_assessments.extend([AIRiskAssessment() for _ in chunk])
            continue

        try:
            batch = AIBatchRiskAssessment.model_validate(parsed)
            assessments = batch.assessments
        except ValidationError:
            # Try bare list
            raw_list = parsed.get("assessments", [])
            assessments = []
            for item_data in raw_list:
                try:
                    assessments.append(AIRiskAssessment.model_validate(item_data))
                except ValidationError:
                    assessments.append(AIRiskAssessment())

        # Pad if LLM returned fewer than expected
        while len(assessments) < len(chunk):
            assessments.append(AIRiskAssessment())

        all_assessments.extend(assessments[: len(chunk)])

    return all_assessments
