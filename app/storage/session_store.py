import json
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_LEFT
from reportlab.lib import colors

BASE_DIR = Path("data/sessions")


def _session_dir(session_id: str) -> Path:
    date_dir = BASE_DIR / datetime.now().strftime("%Y-%m-%d")
    session_dir = date_dir / session_id
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def store_raw_transcript(session_id: str, transcript: List[Dict[str, Any]]) -> None:
    path = _session_dir(session_id) / "raw_transcript.json"
    path.write_text(json.dumps(transcript, ensure_ascii=False, indent=2), encoding="utf-8")


def store_structured_output(session_id: str, structured: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "structured_output.json"
    path.write_text(json.dumps(structured, ensure_ascii=False, indent=2), encoding="utf-8")


def store_metadata(session_id: str, metadata: Dict[str, Any]) -> None:
    path = _session_dir(session_id) / "metadata.json"
    path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")


def _render_section(
    story: list,
    title: str,
    items: list,
    render_item,
    section_style,
    body_style,
):
    story.append(Paragraph(title, section_style))
    if items:
        for item in items:
            story.append(Paragraph(render_item(item), body_style))
    else:
        story.append(Paragraph("—", body_style))


def store_pdf_report(
    session_id: str,
    session_date: str,
    structured_state: dict,
    clinical_report: str,
):
    session_dir = _session_dir(session_id)
    pdf_path = session_dir / "clinical_report.pdf"

    styles = getSampleStyleSheet()
    story: list = []

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

    # ---------------- TITLE ----------------
    story.append(Paragraph("CLINICAL CONSULTATION NOTE", title_style))
    story.append(Spacer(1, 12))

    # ---------------- PATIENT DETAILS ----------------
    patient = structured_state.get("patient", {})
    patient_table = Table(
        [
            ["Patient Name", patient.get("name", "—")],
            ["Age", patient.get("age", "—")],
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
                ("FONT", (0, 0), (-1, -1), "Helvetica"),
            ]
        )
    )

    story.append(patient_table)
    story.append(Spacer(1, 14))

    # ---------------- SECTIONS ----------------
    _render_section(
        story,
        "Chief Complaints",
        structured_state.get("symptoms", []),
        lambda s: f"- {s['name']}" + (f" ({s['duration']})" if s.get("duration") else ""),
        section_style,
        body_style,
    )

    _render_section(
        story,
        "Investigations",
        structured_state.get("investigations", []),
        lambda i: f"- {i['name']}" + (f": {i['value']}" if i.get("value") else ""),
        section_style,
        body_style,
    )

    _render_section(
        story,
        "Tests Advised",
        structured_state.get("tests", []),
        lambda t: f"- {t.get('value') if isinstance(t, dict) else t}",
        section_style,
        body_style,
    )

    _render_section(
        story,
        "Diagnosis",
        structured_state.get("diagnosis", []),
        lambda d: f"- {d.get('value') if isinstance(d, dict) else d}",
        section_style,
        body_style,
    )

    _render_section(
        story,
        "Medications",
        structured_state.get("medications", []),
        lambda m: f"- {m['name']}" + (f" — {m['dosage']}" if m.get("dosage") else ""),
        section_style,
        body_style,
    )

    _render_section(
        story,
        "Advice",
        structured_state.get("advice", []),
        lambda a: f"- {a.get('value') if isinstance(a, dict) else a}",
        section_style,
        body_style,
    )

    # ---------------- CLINICAL SUMMARY ----------------
    story.append(Paragraph("Clinical Summary", section_style))
    if clinical_report:
        for line in clinical_report.split("\n"):
            story.append(Paragraph(line, body_style))
    else:
        story.append(Paragraph("—", body_style))

    # ---------------- FOOTER ----------------
    story.append(Spacer(1, 20))
    story.append(
        Paragraph(
            "Generated AI Report, Doctor verification required.",
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


def store_structured_state(session_id: str, structured_state: dict):
    path = _session_dir(session_id) / "structured_state.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(structured_state, f, ensure_ascii=False, indent=2)
