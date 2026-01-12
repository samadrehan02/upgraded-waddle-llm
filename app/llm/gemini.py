import json
from typing import List, Dict, Any
from google import genai
from app.config import settings
from app.models import TranscriptLine

client = genai.Client(api_key=settings.GEMINI_API_KEY)

EXPECTED_KEYS = {
    "utterances",
    "symptoms",
    "diagnosis",
    "medications",
    "advice",
    "clinical_report",
}


def _format_transcript(transcript: List[TranscriptLine]) -> str:
    lines = []
    for idx, entry in enumerate(transcript, start=1):
        lines.append(f"{idx}. {entry['text']}")
    return "\n".join(lines)


def normalize_with_gemini(
    transcript: List[TranscriptLine],
) -> Dict[str, Any]:
    formatted_transcript = _format_transcript(transcript)

    prompt = f"""
You are a medical conversation parser.

Your task is to analyze a raw ASR transcript and extract structured information.
You must NOT provide medical advice.
You must NOT invent information.

If something is uncertain or ambiguous, mark it as "unknown".
Do not assume speaker roles unless strongly implied by language.

Transcript:
{formatted_transcript}

Tasks:
1. For each utterance, classify the speaker as:
   - patient
   - doctor
   - unknown

2. Extract structured clinical information:
   - symptoms (with duration if mentioned)
   - medications (with dosage if mentioned)
   - diagnosis (only if explicitly stated)
   - advice (only if explicitly stated)

3. Generate a short clinical report in Hindi.

Return ONLY valid JSON.
Do NOT include markdown.
Do NOT include explanations.

ALLOWED JSON SCHEMA (EXACT):
{{
  "utterances": [
    {{
      "index": 1,
      "speaker": "patient | doctor | unknown",
      "text": "string",
    }}
  ],
  "symptoms": [
    {{
      "name": "string",
      "duration": "string or null"
    }}
  ],
  "diagnosis": ["string"],
  "medications": [
    {{
      "name": "string",
      "dosage": "string or null"
    }}
  ],
  "advice": ["string"],
  "clinical_report": "string or null"
}}
"""

    try:
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config={"temperature": 0.0},
        )
    except Exception as e:
        return {
            "model": settings.GEMINI_MODEL,
            "error": "llm_call_failed",
            "details": str(e),
            "prompt_version": "v3",
        }

    raw_text = (response.text or "").strip()
    sanitized = False

    # Defensive markdown stripping
    if raw_text.startswith("```"):
        sanitized = True
        raw_text = raw_text.strip().lstrip("`").rstrip("`")
        if raw_text.lower().startswith("json"):
            raw_text = raw_text[4:].strip()

    try:
        parsed = json.loads(raw_text)
    except json.JSONDecodeError:
        return {
            "model": settings.GEMINI_MODEL,
            "error": "invalid_json",
            "raw_text": raw_text,
        }

    if not isinstance(parsed, dict) or set(parsed.keys()) != EXPECTED_KEYS:
        return {
            "model": settings.GEMINI_MODEL,
            "error": "schema_violation",
            "raw_text": raw_text,
        }

    return {
        "model": settings.GEMINI_MODEL,
        "data": parsed,
    }