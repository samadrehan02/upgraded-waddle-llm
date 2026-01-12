# Hindi Medical Transcription & Clinical Note Assistant

A **real-time Hindi medical transcription system** that converts live doctor–patient conversations into structured clinical data and a draft OPD note.

This system is **not a diagnostic tool** and **does not provide medical advice**.  
It is a **documentation assistant** designed to reduce manual note-taking.

---

## What This Project Does

- Captures live audio from the browser
- Performs **real-time Hindi speech-to-text** using Vosk
- Displays **partial and final transcripts** instantly
- Sends the completed transcript to an LLM (Gemini) for **structured extraction**
- Applies **strict trust and validation rules**
- Stores **every session** for audit, replay, and debugging
- Generates a **draft Hindi clinical report** for doctor review

---

## Core Architecture

### High-Level Flow

Browser Microphone
        ↓ (WebSocket, PCM audio)
FastAPI Server
        ↓
Vosk ASR (Hindi)
        ↓
Raw Transcript (Immutable)
        ↓
Gemini LLM (Parser Only)
        ↓
Trust & Validation Layer
        ↓
Structured Output / Draft Report
        ↓
Audit-First Storage

## Architecture Layers

### 1. Frontend (Browser)

**Files**
- `templates/index.html`
- `static/app.js`
- `static/style.css`

**Responsibilities**
- Capture microphone audio
- Convert audio to 16-bit PCM @ 16 kHz
- Stream audio via WebSocket
- Display:
  - live partial ASR text
  - final transcript lines
  - structured JSON
  - generated clinical note

**Design Principle**
> The frontend is a dumb renderer.  
> No interpretation, no medical logic.

---

### 2. Transport Layer (WebSocket)

**File**
- `app/api/websocket.py`

**Responsibilities**
- Session creation (`session_id`)
- Streaming audio → ASR
- Emitting events to UI:
  - `partial`
  - `transcript`
  - `structured`
- Triggering post-processing on `stop`

---

### 3. Speech Recognition (ASR)

**File**
- `app/asr/vosk_adapter.py`

**Technology**
- Vosk Hindi model (`vosk-model-hi-0.22`)

**Behavior**
- Emits:
  - partial hypotheses (low latency)
  - finalized utterances (committed)
- No speaker detection
- No rewriting
- No medical logic

---

## Raw Transcript (Ground Truth)

This transcript:

- Is immutable  
- Is never overwritten  
- Acts as the single source of truth for all downstream logic  

---

## 5. LLM Normalization Layer

**File**
app/llm/gemini.py

**Role**  
Parse the raw transcript into structured clinical data.

**Tasks**
- Speaker classification (`patient / doctor / unknown`)
- Symptom extraction (with duration)
- Medication extraction (with dosage)
- Diagnosis detection (explicit only)
- Generate a short Hindi clinical report

**Hard Constraints**
- Temperature = `0.0`
- Strict JSON schema
- No markdown
- No explanations
- No assumptions

The LLM is treated strictly as a **parser**, not an authority.


## 6. Trust & Validation Layer

**File**
app/pipeline/trust.py

markdown
Copy code

**Purpose**  
Decide whether LLM output is allowed to be surfaced.

**Rules**
- Patient speech must exist
- Doctor speech required for medications and diagnoses
- Symptoms must be grounded in patient speech
- Violations downgrade or block output

**Decisions**
- `use_llm` – full report allowed
- `partial_llm` – symptoms only
- `ignore_llm` – nothing shown

Safety always wins over completeness.

---

## 7. Evaluation & Normalization

**Files**
app/pipeline/normalize.py
app/pipeline/evaluate.py


**Role**
- Wrap LLM output into a single evaluation record
- Attach trust decisions and metadata
- Produce an auditable result per session

---

## 8. Persistence (Audit-First)

**File**
app/storage/session_store.py

**Stored Per Session**
- `raw_transcript.json`
- `structured_output.json`
- `metadata.json`

**Properties**
- Append-only
- Date-partitioned
- Human-readable JSON
- No data is silently discarded

---

## Features

- Real-time Hindi speech-to-text
- Live partial transcript display
- Strict LLM schema enforcement
- Trust-gated clinical extraction
- Draft Hindi OPD note generation
- Full session audit trail
- Safe and explicit failure modes

---

## What This Project Is NOT

- ❌ Not a diagnostic engine  
- ❌ Not a prescription system  
- ❌ Not an autonomous medical agent  
- ❌ Not a certified medical device  

Doctors remain the final authority.

---

## Installation

### 1. Clone the repository
```bash
git clone <repository-url>
cd <repository-name>
2. Create and activate virtual environment
bash
Copy code
python -m venv .venv
source .venv/bin/activate    # Linux / macOS
# OR
.venv\Scripts\activate       # Windows
```
### 3. Install dependencies
```bash
pip install -r requirements.txt
```
### 4. Download Vosk Hindi model

Download and extract:

vosk-model-hi-0.22
Place it at:
```bash
models/vosk/hi/vosk-model-hi-0.22/
```
### 5. Configure environment variables
Create a .env file:
```bash

env
Copy code
ENV=dev
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-1.5-pro
Running the Application
Development (recommended):
```

uvicorn main:app --reload
Open in browser:

```bash

http://localhost:8000
```
Alternative (no auto-reload):

```bash

python main.py
```
## Project Structure
```bash

.
├── main.py
├── app/
│   ├── api/
│   ├── asr/
│   ├── llm/
│   ├── pipeline/
│   ├── storage/
│   ├── models.py
│   └── config.py
├── templates/
├── static/
├── models/
├── data/
└── requirements.txt
```

## Design Principles

- Raw data is never overwritten

- LLM output is never blindly trusted

- Failures are explicit and visible

- Safety over completeness

- Auditability over convenience

## Status
This project is a functional proof-of-concept with a stable, extensible architecture suitable for further hardening and productionization.