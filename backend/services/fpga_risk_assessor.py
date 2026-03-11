"""AI-powered SI/PI risk assessment for FPGA pin swaps.

Each pin swap receives a risk classification:
  - "High Risk: …"   → pin AND/OR bank change with SI/PI concern
  - "Medium Risk: …"  → bank change or moderate concern
  - "Low Risk: …"     → intra-bank move, minimal impact
"""
import json
from typing import List

from services.ai_client import get_client, get_model


_SYSTEM_PROMPT = """\
You are an expert Signal Integrity / Power Integrity (SI/PI) engineer reviewing \
FPGA pin swap proposals for an aerospace digital hardware design.

You will receive a JSON array of pin swaps. Each object has:
  Signal_Name, Old_Pin, New_Pin, Old_Bank, New_Bank.

For EVERY swap, provide a risk assessment using EXACTLY one of these prefixes:
  - "High Risk: <explanation>"   — use when pin AND bank change, high-speed signals \
cross banks, VCCIO domains differ, or timing skew is likely.
  - "Medium Risk: <explanation>" — use when only the bank changes, or the move has \
moderate SI/PI implications (e.g. different I/O standard possible).
  - "Low Risk: <explanation>"    — use when pin moves within the same bank or the \
change has negligible SI/PI impact.

You MUST return a JSON object matching this schema:
{
  "assessments": [
    {
      "Signal_Name": "<string — must match the input exactly>",
      "AI_Risk_Assessment": "<string — must start with 'High Risk:', 'Medium Risk:', or 'Low Risk:'>"
    }
  ]
}

Return ONLY the JSON object. No prose, no markdown code fences, no commentary."""


def assess_pin_risks(swapped_pins: List[dict]) -> List[dict]:
    """Analyse a list of pin swap dicts and populate AI_Risk_Assessment.

    Args:
        swapped_pins: List of dicts with keys Signal_Name, Old_Pin, New_Pin,
                      Old_Bank, New_Bank, AI_Risk_Assessment (initially None).

    Returns:
        The same list with AI_Risk_Assessment filled in from LLM response.

    Raises:
        RuntimeError: If INTERNAL_API_KEY is not configured.
        Exception:    Propagated from the OpenAI client for network/API errors.
    """
    if not swapped_pins:
        return []

    client = get_client()
    model = get_model()

    # Build a compact representation for the prompt (strip the null risk field)
    swap_summary = [
        {
            "Signal_Name": s["Signal_Name"],
            "Old_Pin": s["Old_Pin"],
            "New_Pin": s["New_Pin"],
            "Old_Bank": s["Old_Bank"],
            "New_Bank": s["New_Bank"],
        }
        for s in swapped_pins
    ]

    response = client.chat.completions.create(
        model=model,
        response_format={"type": "json_object"},
        temperature=0.0,
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Assess the SI/PI risk for each of the following FPGA pin swaps:\n\n"
                    + json.dumps(swap_summary, indent=2)
                ),
            },
        ],
    )

    raw_json = response.choices[0].message.content

    try:
        parsed = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM returned non-JSON content: {exc}") from exc

    # Build a lookup from the AI response
    assessments = parsed.get("assessments", [])
    risk_map = {a["Signal_Name"]: a["AI_Risk_Assessment"] for a in assessments}

    # Merge back into the original swap dicts
    for swap in swapped_pins:
        swap["AI_Risk_Assessment"] = risk_map.get(swap["Signal_Name"])

    return swapped_pins
