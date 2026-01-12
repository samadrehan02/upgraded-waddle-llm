# Hindi Medical Transcription & Clinical Note Assistant

This project is a **real-time Hindi medical transcription system** designed to assist doctors in high-volume, low-resource settings by automatically generating structured clinical notes from spoken conversations.

It is **not an autonomous medical system**.  
It is a **documentation assistant** that reduces manual note-taking.

---

## High-Level Overview

The system listens to a live medical conversation, converts speech to text, extracts clinically relevant information using an LLM, and generates a draft clinical report for the doctor.

At every stage:
- Raw data is preserved
- No medical facts are invented
- Trust and validation rules gate what is shown

---

## Core Architecture

### 1. Audio & Speech Recognition (ASR)
- Browser captures live audio
- Audio is streamed to the backend via WebSocket
- **Vosk** performs real-time Hindi speech-to-text
- Raw transcript is shown immediately to the user

This layer is intentionally **dumb**:
- No speaker guessing
- No interpretation
- No rewriting

---

### 2. Language Model Interpretation (LLM)
After the consultation ends:
- The raw transcript is sent to **Gemini**
- The LLM performs:
  - Speaker classification (patient / doctor / unknown)
  - Symptom extraction (with duration)
  - Medication extraction (with dosage)
  - Diagnosis detection (only if explicitly stated)
  - Clinical report generation (Hindi)

The LLM is treated as a **read-only interpreter**, not a source of truth.

---

### 3. Trust & Validation Layer
Before any output is surfaced:
- LLM output is validated against strict rules
- Examples:
  - Medications require doctor presence
  - Symptoms must be grounded in patient speech
  - Diagnoses must be explicitly stated

The system decides whether to:
- Use the LLM output
- Partially use it
- Ignore it entirely

---

### 4. Persistence (Audit-First)
Every session is stored automatically:
- Raw ASR transcript
- LLM structured output
- Metadata (model, prompt version, timestamps)

Storage is **append-only** and **session-based**, enabling:
- Audits
- Debugging
- Replay
- Future model re-runs

No data is silently discarded.

---

### 5. User Interface
The UI is a lightweight web app that shows:
- Live transcript (real-time ASR)
- Structured data (post-processing)
- Generated clinical note

The doctor always sees:
- What was said
- What was inferred
- What was generated

---

## Separation of Concerns

| Layer | Responsibility |
|------|---------------|
| ASR (Vosk) | Speech → text |
| UI | Display raw and structured data |
| LLM (Gemini) | Interpretation & normalization |
| Trust Logic | Safety & validation |
| Storage | Persistent session records |

Each layer can be modified or replaced independently.

---

## Design Principles

- **No hallucinated medical facts**
- **Raw data is never overwritten**
- **LLM output is never blindly trusted**
- **Doctor remains the final authority**
- **System failure degrades safely**

---

## What This System Is NOT

- ❌ A diagnostic engine
- ❌ A prescription system
- ❌ A replacement for medical judgment
- ❌ A production-certified medical device

It is a **documentation assistant**, nothing more.

---

## Intended Use Case

- Remote or rural clinics
- High patient throughput
- Limited time for manual documentation
- Doctors who need *draft notes*, not final decisions

---

## Future Directions (Optional)

- Session replay & analytics
- Prompt versioning experiments
- Confidence scoring
- Database-backed storage
- Integration with EMR systems

---

## Status

This project is currently a **functional proof-of-concept** with:
- Real-time ASR
- LLM-based normalization
- Trust gating
- Persistent storage
- Usable UI

The architecture is stable and extensible.
