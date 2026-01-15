# Changelog

## 2026-01-14

### Architecture & Flow

- Finalized a **streaming scribe architecture**:

  - Browser microphone → WebSocket → Vosk ASR (Hindi)
  - Incremental LLM parsing during pauses
  - Final report generation only on session stop
- Eliminated periodic report regeneration to reduce latency and cost.
- Implemented silence-based triggering with throttling for incremental updates.

---

### WebSocket & ASR Pipeline

- Stabilized WebSocket lifecycle handling:

  - Proper session scoping
  - Graceful disconnect handling
  - Background silence watcher task with cancellation
- Added incremental structured-state updates off the event loop using executors to prevent UI freezes.
- Introduced throttling (`MIN_UPDATE_INTERVAL`) with **forced final update on STOP** to prevent data loss.

---

### Structured State & Incremental LLM

- Introduced a persistent **structured state** that is updated incrementally instead of regenerated.
- Removed unused trust layer logic after scoping system to AI scribe only.
- Fixed multiple failure modes:
  - Empty LLM responses
  - Invalid JSON responses
  - Schema drift
  - Missing utterance indices
- Hardened incremental merging logic to prevent:
  - Data loss
  - Duplicate processing
  - KeyErrors on malformed utterances

---

### Patient Metadata Extraction

- Added explicit-only extraction of patient demographics from transcript:
  - `name`
  - `age`
  - `gender`
- Enforced strict rules:
  - No guessing
  - No inference
  - No overwriting unless explicitly re-stated
- Integrated patient metadata into:
  - Structured state
  - Metadata store
  - PDF report

---

### Report Generation

- Decoupled:
  - Incremental extraction
  - Final clinical report generation
- Optimized final report latency (reduced from ~10–12s to ~3–5s typical).
- Standardized report generation as a **single blocking call at STOP**.

---

### PDF Generation & Storage

- Implemented OPD-style PDF generation using ReportLab.
- PDFs include:
  - Patient name, age, gender
  - Symptoms with duration
  - Diagnosis
  - Medications with dosage
  - Doctor advice
- Fixed ReportLab path handling on Windows (`Path → str`).
- PDFs are stored per session in a date-partitioned directory structure.

---

### Storage & Audit

- Enforced audit-first storage model:
  - `raw_transcript.json`
  - `structured_state.json`
  - `structured_output.json`
  - `metadata.json`
  - `clinical_report.pdf`
- Fixed missing storage functions (`store_structured_state`).
- Added patient snapshot to metadata for auditability.

---

### Backend Serving

- Mounted `data/` directory as static files in FastAPI.

- Enabled direct PDF downloads via browser without custom endpoints.
- Fixed 404 errors on valid PDF URLs.

---

### Frontend

- Simplified frontend flow:
  - Removed obsolete REST endpoint for report generation.
  - Clinical report now arrives directly via WebSocket payload.
- Added PDF download link handling in UI.
- Preserved live partial ASR display and final transcript rendering.
- Cleaned up UI state handling for recording / processing / ready states.

---

### Stability & Cleanup

- Removed dead code and unused endpoints.
- Fixed multiple race conditions and blocking calls.
- Ensured all long-running operations are executor-isolated.
- Confirmed system stability under continuous speech sessions.

---

### Status

- **v1 feature-complete**
- End-to-end flow validated:
  - Speech → ASR → Structured extraction → Final report → PDF → Download
- System is stable, auditable, and ready to be frozen or extended later.

## 2026-01-15

### Added

- **Streaming AI Scribe Architecture**
  - Real-time Hindi speech-to-text using Vosk
  - Incremental structured data extraction during pauses
  - Final authoritative processing on session stop

- **Speaker Attribution Pipeline**
  - Incremental best-effort speaker labeling
  - Final deterministic speaker normalization pass
  - Prevents patient/doctor speech contamination

- **Patient Demographics Extraction**
  - Dedicated extraction for patient name, age, and gender
  - Extracted only from patient utterances
  - Single-assignment, non-overwriting behavior
  - Stabilized PDF rendering of patient details

- **Medical Tests / Investigations Section**
  - Structured extraction of investigations (e.g. X-ray, blood tests)
  - Captures test name, result, and interpretation when stated
  - Proper separation from diagnosis
  - Displayed in structured state and PDF report

- **Diagnosis Specificity Improvements**
  - Preserves explicitly stated diagnosis details
  - Supports location, side, and type (e.g. “left leg fracture”, “tibia fracture”)
  - No inference or generalization

- **Findings vs Diagnosis Separation**
  - Investigations represent evidence
  - Diagnosis represents clinical conclusion
  - Prevents duplication of test results as diagnoses

- **Confidence Tagging (Internal)**
  - Per-section confidence metadata (high / medium / low)
  - Applied to symptoms, diagnosis, medications, tests
  - Internal-only, not exposed to UI or PDF

- **Clinical PDF Report Generation**
  - Structured doctor-style consultation note
  - Sections:
    - Patient details
    - Chief complaints
    - Investigations
    - Diagnosis
    - Medications
    - Advice
    - Clinical summary
  - Stored per session with date-based directory structure

- **Audit-First Storage**
  - Append-only session storage
  - Human-readable JSON outputs:
    - raw_transcript.json
    - structured_state.json
    - structured_output.json
    - metadata.json
    - clinical_report.pdf

---

### Changed

- Replaced REST-based report generation with WebSocket-only flow
- Throttled incremental LLM calls to reduce latency and UI freezing
- Moved heavy LLM operations to background executors
- Ensured final report generation is fast and deterministic
- Improved schema normalization to prevent data loss on partial failures

---

### Fixed

- Latency spikes caused by overlapping incremental LLM calls
- UI freezes due to blocking operations
- Speaker attribution failures during throttled updates
- Empty or partially filled structured state
- PDF font rendering issues (Unicode / box characters)
- Missing PDF downloads due to static routing misconfiguration
- Broken prompt formatting caused by f-string JSON schemas
- Incorrect session directory naming
- Data not being persisted correctly across sessions

---

### Removed

- Deprecated REST endpoint for report generation
- Unused trust / validation layer originally meant for clinical suggestions
- Redundant or dead pipeline components

---

### Architectural Notes

- Raw transcript is immutable and remains the single source of truth
- LLMs are treated strictly as parsers, not authorities
- Safety, auditability, and determinism prioritized over completeness
- Doctors remain the final decision-makers

---
