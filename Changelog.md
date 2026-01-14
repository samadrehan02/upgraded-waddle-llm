# Changelog

## 2026-01-14 — Streaming Medical Scribe v1 Completed

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
