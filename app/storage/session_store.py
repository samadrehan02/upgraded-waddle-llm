import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

BASE_DIR = Path("data/sessions")

pdfmetrics.registerFont(
    TTFont("NotoDeva", "static/fonts/NotoSansDevanagari-Regular.ttf")
)

def _session_dir(session_id: str) -> Path:
    date_dir = BASE_DIR / datetime.now().strftime("%Y-%m-%d")
    session_dir = date_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir

def store_raw_transcript(session_id: str, transcript: List[Dict[str, Any]]) -> None:
    path = _session_dir(session_id) / "raw_transcript.json"
    path.write_text(
        json.dumps(transcript, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def store_structured_output(session_id: str, structured: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "structured_output.json"
    path.write_text(
        json.dumps(structured, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def store_structured_state(session_id: str, structured_state: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "structured_state.json"
    path.write_text(
        json.dumps(structured_state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def store_metadata(session_id: str, metadata: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "metadata.json"
    path.write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def store_pdf_report(
    session_id: str,
    session_date: str,
    structured_state: Dict[str, Any],
    clinical_report: str,
) -> Path:

    session_dir = _session_dir(session_id)
    pdf_path = session_dir / "clinical_report.pdf"

    styles = getSampleStyleSheet()

    # Ensure Unicode font everywhere
    for style in styles.byName.values():
        style.fontName = "NotoDeva"

    title_style = ParagraphStyle(
        "Title",
        parent=styles["Heading1"],
        alignment=TA_LEFT,
        spaceAfter=12,
    )

    section_style = ParagraphStyle(
        "Section",
        parent=styles["Heading3"],
        spaceBefore=12,
        spaceAfter=6,
    )

    body_style = styles["Normal"]

    story: List[Any] = []


    story.append(Paragraph("CLINICAL CONSULTATION NOTE", title_style))
    story.append(Spacer(1, 12))

    patient = structured_state.get("patient", {})

    patient_table = Table(
        [
            ["Patient Name", patient.get("name") or "—"],
            ["Age", patient.get("age") or "—"],
            ["Date", session_date],
            ["Session ID", session_id],
        ],
        colWidths=[120, 350],
    )

    patient_table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("BACKGROUND", (0, 0), (0, -1), colors.whitesmoke),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("FONT", (0, 0), (-1, -1), "NotoDeva"),
            ]
        )
    )

    story.append(patient_table)
    story.append(Spacer(1, 14))

    symptoms = structured_state.get("symptoms", [])
    if symptoms:
        story.append(Paragraph("Chief Complaints", section_style))
        for s in symptoms:
            line = f"- {s.get('name')}"
            if s.get("duration"):
                line += f" ({s['duration']})"
            story.append(Paragraph(line, body_style))

    tests = structured_state.get("tests", [])
    if tests:
        story.append(Paragraph("Investigations", section_style))
        for t in tests:
            line = f"- {t.get('test_name')}"
            if t.get("result"):
                line += f": {t['result']}"
            if t.get("note"):
                line += f" ({t['note']})"
            story.append(Paragraph(line, body_style))

    diagnosis = structured_state.get("diagnosis", [])
    if diagnosis:
        story.append(Paragraph("Diagnosis", section_style))
        for d in diagnosis:
            story.append(Paragraph(f"- {d}", body_style))

    medications = structured_state.get("medications", [])
    if medications:
        story.append(Paragraph("Medications", section_style))
        for m in medications:
            line = f"- {m.get('name')}"
            if m.get("dosage"):
                line += f" — {m['dosage']}"
            story.append(Paragraph(line, body_style))

    advice = structured_state.get("advice", [])
    if advice:
        story.append(Paragraph("Advice", section_style))
        for a in advice:
            story.append(Paragraph(f"- {a}", body_style))

    if clinical_report:
        story.append(Paragraph("Clinical Summary", section_style))
        for line in clinical_report.split("\n"):
            story.append(Paragraph(line, body_style))

    story.append(Spacer(1, 20))
    story.append(
        Paragraph(
            "Generated by AI Scribe — Draft only. Doctor verification required.",
            styles["Italic"],
        )
    )

    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=A4,
        rightMargin=36,
        leftMargin=36,
        topMargin=36,
        bottomMargin=36,
    )

    doc.build(story)
    return pdf_path