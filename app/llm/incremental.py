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
        "patient": current_state.get("patient",{}),
        "symptoms": current_state.get("symptoms", []),
        "medications": current_state.get("medications", []),
        "diagnosis": current_state.get("diagnosis", []),
        "advice": current_state.get("advice", []),
        "investigations": current_state.get("investigations", []),
        "tests": current_state.get("tests", []),
    }

    utterance_texts = [
        u["text"]
        for u in new_utterances
        if "text" in u
    ]

    prompt = f"""
You are updating an existing structured medical record.

Patient Demographics (STRICT):
- Extract patient name ONLY if the patient explicitly states their own name.
  Examples:
  - "My name is Rahul"
  - "मेरा नाम राहुल है"
- Extract age ONLY if explicitly stated as a number.
  Examples:
  - "I am 32 years old"
  - "मेरी उम्र 32 साल है"
- Extract gender ONLY if explicitly stated.
  Examples:
  - "I am male"
  - "मैं पुरुष हूँ"

Rules:
- Do NOT guess or infer.
- Do NOT overwrite existing patient fields unless a new explicit statement is made.
- If unsure, leave the field unchanged.

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
  - investigations (vitals or measurements with values)
  - tests (investigations advised by the doctor)

Investigations:
- Extract only objective measurements stated explicitly
- Examples:
  - "temperature is 100"
  - "BP 120 by 80"
- Store as:
  {{ "name": "body temperature", "value": "100 F" }}

Tests:
- Extract ONLY when doctor advises tests
- Examples:
  - "blood test karwa liye"
  - "CBC karwa lo"
- Normalize to English test names

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

NEW UTTERANCES(raw text only):
{json.dumps(utterance_texts, ensure_ascii=False)}

Return a JSON object with the following optional fields:
- patient
- symptoms
- medications
- diagnosis
- advice
- investigations
- tests

The "patient" field, if present, must be an object with:
- name (string or null)
- age (number or null)
- gender (string or null)


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
