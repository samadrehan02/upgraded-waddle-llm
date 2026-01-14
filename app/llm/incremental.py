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
- Do NOT modify or remove existing utterances.
- Do NOT change speaker labels of existing utterances.
- Do NOT remove existing clinical facts unless explicitly contradicted.
- If unsure about speaker or facts, use "unknown" or leave fields unchanged.
- Do NOT infer diagnoses.
- Return ONLY valid JSON.
- Do NOT include explanations or markdown.

CURRENT STATE:
{json.dumps(llm_state, ensure_ascii=False)}

NEW UTTERANCES:
{json.dumps(new_utterances, ensure_ascii=False)}

Return the UPDATED structured state using the SAME JSON SCHEMA.
"""

    response = client.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config={"temperature": 0.0},
    )

    raw_text = (response.text or "").strip()

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
