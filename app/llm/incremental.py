import json
from typing import Dict, Any, List

from google import genai
from app.config import settings
from app.pipeline.schema import normalize_structured_state
from app.pipeline.schema import merge_utterances_with_speakers

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def update_structured_state(
    current_state: Dict[str, Any],
    new_utterances: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Incrementally update structured clinical state using new utterances.
    Returns updated structured state.
    """
    llm_state = {
        "symptoms": current_state.get("symptoms", []),
        "medications": current_state.get("medications", []),
        "diagnosis": current_state.get("diagnosis", []),
        "advice": current_state.get("advice", []),
    }

    prompt = f"""
You are updating an existing structured medical record.

You are given:
1. The current structured state (JSON)
2. New transcript utterances since the last update

Tasks:
- Assign a speaker to each NEW utterance:
  - "patient"
  - "doctor"
  - or "unknown"
- Update structured clinical information based ONLY on new utterances:
  - symptoms (with duration if mentioned)
  - medications (with dosage if mentioned)
  - diagnosis (ONLY if explicitly stated)
  - advice (ONLY if explicitly stated)

Rules:
- Update the structured state based on the new utterances only.
- Identify and extract symptoms, medications, diagnosis, and advice
  from the new utterances when they are explicitly stated.
- It is acceptable to return the same structured state
  if no new clear information is present.
- Do NOT invent or infer facts.
- Diagnosis MUST be added only if explicitly stated.
- If unsure, leave fields unchanged.
- Speaker may be "unknown" if unclear.

Example:

If the new utterance is:
"मुझे दो दिन से बुखार है"

Then the structured update should include:
{{
  "symptoms": [
    {{ "name": "fever", "duration": "two days" }}
  ]
}}
CURRENT STATE:
{json.dumps(llm_state, ensure_ascii=False)}

NEW UTTERANCES:
{json.dumps(new_utterances, ensure_ascii=False)}

Return a JSON object with the following optional fields:
- symptoms
- medications
- diagnosis
- advice

Include a field ONLY if it should be added or updated.
Do NOT remove existing data.
"""

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config={"temperature": 0.0},
    )

    raw_text = (response.text or "").strip()

    if not raw_text:
        raise ValueError("empty_llm_response")

    if raw_text.startswith("```"):
        raw_text = raw_text.strip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    parsed = json.loads(raw_text)

    normalized = normalize_structured_state(
        previous=current_state,
        candidate=parsed,
    )

    normalized["utterances"] = merge_utterances_with_speakers(
        previous_utterances=current_state["utterances"],
        updated_utterances=normalized["utterances"],
    )

    return normalized
