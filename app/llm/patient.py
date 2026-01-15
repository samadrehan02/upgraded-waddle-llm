import json
from typing import Dict, List
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def extract_patient_demographics(utterances: List[Dict]) -> Dict[str, str | None]:
    """
    Extract patient name, age, gender ONLY from patient speech.
    Runs once. Never overwrites existing values.
    """

    patient_utterances = [
        u["text"]
        for u in utterances
        if u.get("speaker") == "patient"
    ]

    if not patient_utterances:
        return {"name": None, "age": None, "gender": None}

    prompt = f"""
You are extracting patient demographics from a medical conversation.

ONLY extract if the patient explicitly states:
- name
- age
- gender

Rules:
- Use ONLY patient speech
- Do NOT guess
- Do NOT infer
- If missing, return null
- Return ONLY valid JSON
- No markdown, no explanation

PATIENT UTTERANCES:
{json.dumps(patient_utterances, ensure_ascii=False)}

Return EXACTLY:
{{
  "name": "string or null",
  "age": "number or null",
  "gender": "male | female | other | null"
}}
"""

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config={"temperature": 0.0},
    )

    raw = (response.text or "").strip()

    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()

    return json.loads(raw)
