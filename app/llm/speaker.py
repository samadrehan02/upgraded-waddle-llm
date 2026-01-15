import json
from typing import List, Dict
from google import genai
from app.config import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)


def assign_speakers(utterances: List[Dict]) -> List[Dict]:
    """
    Final authoritative speaker assignment.
    DOES NOT extract clinical info.
    """

    prompt = f"""
You are assigning speakers in a medical conversation.

For EACH utterance, assign exactly one speaker:
- patient
- doctor
- unknown

Rules:
- Do NOT invent speakers.
- Use only linguistic cues.
- If unclear, use "unknown".
- Do NOT change text or order.
- Return ONLY valid JSON.
- No markdown. No explanations.

UTTERANCES:
{json.dumps(utterances, ensure_ascii=False)}

Return:
[
  {{
    "index": number,
    "speaker": "patient | doctor | unknown"
  }}
]
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

def apply_speaker_labels(utterances, speaker_map):
    by_index = {u["index"]: u for u in utterances}

    for s in speaker_map:
        idx = s["index"]
        if idx in by_index:
            by_index[idx]["speaker"] = s["speaker"]

    return list(by_index.values())