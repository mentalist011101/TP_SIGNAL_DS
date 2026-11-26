"""Export des résultats d'une analyse terminée en JSON, CSV ou PDF (EF-09, C26).

Une fonction par format, qui renvoie les octets du fichier. La route ne fait qu'appeler
build_export et envoyer le fichier.

- JSON : le détail de l'analyse, tel que le renvoie GET /api/v1/analyses/{id}. Ce détail est
  construit par le schéma de l'API ; la route le passe tout prêt, pour que services/ n'importe
  pas l'API.
- CSV : format long, une ligne par probabilité (globale ou de segment).
- PDF : une à deux pages en français, avec le spectrogramme déjà enregistré.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from echolens.services.storage import AnalysisRecord, AnalysisStatus

EXPORT_FORMATS = ["json", "csv", "pdf"]
# Flask ajoute lui-même « ; charset=utf-8 » aux types text/* (donc au CSV).
MIMETYPES = {
    "json": "application/json; charset=utf-8",
    "csv": "text/csv",
    "pdf": "application/pdf",
}
CSV_COLUMNS = [
    "analysis_id",
    "task",
    "scope",
    "segment_index",
    "start_s",
    "end_s",
    "rank",
    "label",
    "label_fr",
    "probability",
    "model_id",
    "model_version",
    "calibrated",
    "text",
]
TASK_TITLES = {
    "emotion": "Émotion",
    "sound_event": "Événement sonore",
    "transcription": "Transcription",
    "speaker": "Locuteur",
}
PROFILE_TITLES = {"quality": "Qualité", "realtime": "Temps réel"}
STATUS_TITLES = {
    AnalysisStatus.PENDING: "en attente",
    AnalysisStatus.PROCESSING: "en cours",
    AnalysisStatus.FAILED: "en échec",
}
DEMO_MODEL_ID = "demo"
DEMO_BANNER = "Résultats de démonstration, pas de vrais modèles"
# Le PDF tient en une à deux pages : 3 classes par tâche, et au plus 12 segments par tâche
# (les autres sont dans l'export CSV).
TOP_CLASS_COUNT = 3
MAX_PDF_SEGMENTS = 12
# Le spectrogramme (une colonne par trame de 10 ms) est étiré sur la largeur utile de la page.
PAGE_MARGIN = 2 * cm
SPECTROGRAM_HEIGHT = 4 * cm
SECONDS_PER_MINUTE = 60


class AnalysisNotDoneError(ValueError):
    """L'analyse n'est pas terminée : il n'y a pas encore de résultats à exporter."""


@dataclass(frozen=True)
class ExportFile:
    """Fichier prêt à télécharger : contenu, type MIME et nom proposé."""

    content: bytes
    mimetype: str
    filename: str


def build_export(
    record: AnalysisRecord,
    export_format: str,
    detail: dict[str, Any],
    spectrogram_path: Path,
) -> ExportFile:
    """Fichier d'export d'une analyse terminée (EF-09).

    detail : le détail de l'analyse sérialisé par l'API (utilisé seulement pour le JSON).
    Lève AnalysisNotDoneError (message en français) si l'analyse n'est pas terminée.
    """
    check_is_done(record)
    if export_format == "json":
        content = json_export(detail)
    elif export_format == "csv":
        content = csv_export(record)
    else:
        content = pdf_export(record, spectrogram_path)
    filename = export_filename(record, export_format)
    return ExportFile(content=content, mimetype=MIMETYPES[export_format], filename=filename)


def check_is_done(record: AnalysisRecord) -> None:
    """Lève AnalysisNotDoneError si l'analyse n'a pas le statut done."""
    if record.status == AnalysisStatus.DONE:
        return
    status_title = STATUS_TITLES[AnalysisStatus(record.status)]
    raise AnalysisNotDoneError(
        f"Export impossible : l'analyse est {status_title}. Les résultats ne peuvent être "
        "exportés qu'une fois l'analyse terminée."
    )


def export_filename(record: AnalysisRecord, extension: str) -> str:
    """« echolens_<nom d'origine sans extension>_<AAAA-MM-JJ>.<ext> ».

    Le nom d'origine est déjà nettoyé à l'import (caractères sûrs uniquement, S6). La date
    est celle de l'analyse.
    """
    stem = Path(record.original_filename).stem
    day = record.created_at.date().isoformat()
    return f"echolens_{stem}_{day}.{extension}"


def json_export(detail: dict[str, Any]) -> bytes:
    """Le détail de l'analyse, indenté, en UTF-8 (accents écrits tels quels)."""
    text = json.dumps(detail, ensure_ascii=False, indent=2)
    return text.encode("utf-8")


def csv_export(record: AnalysisRecord) -> bytes:
    """Résultats au format long : une ligne par probabilité, globale puis de chaque segment.

    UTF-8 avec BOM (pour qu'Excel reconnaisse les accents), séparateur virgule, point décimal.
    Une tâche sans résultat (no_speech, unavailable) a une seule ligne, avec son statut.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    results = record.results or {}
    for task, result in results.items():
        rows = _task_csv_rows(record.id, task, result)
        writer.writerows(rows)
    text = buffer.getvalue()
    return text.encode("utf-8-sig")


def pdf_export(record: AnalysisRecord, spectrogram_path: Path) -> bytes:
    """Rapport PDF en français : en-tête, spectrogramme, puis une partie par tâche.

    Polices de base de reportlab (Helvetica) : leur codage couvre les accents du français.
    """
    styles = _pdf_styles()
    results = record.results or {}
    # Étape 1 : en-tête, bandeau de démonstration éventuel, spectrogramme.
    story: list[Flowable] = []
    story.extend(_header_flowables(record, styles))
    if _has_demo_result(results):
        story.append(_demo_banner(styles))
    story.extend(_spectrogram_flowables(spectrogram_path, styles))
    # Étape 2 : une partie par tâche demandée.
    for task, result in results.items():
        story.extend(_task_flowables(task, result, styles))
    # Étape 3 : mise en page A4 en mémoire.
    buffer = io.BytesIO()
    document = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=PAGE_MARGIN,
        rightMargin=PAGE_MARGIN,
        topMargin=PAGE_MARGIN,
        bottomMargin=PAGE_MARGIN,
        title=f"EchoLens — {record.original_filename}",
    )
    document.build(story)
    return buffer.getvalue()


def _task_csv_rows(analysis_id: str, task: str, result: dict[str, Any]) -> list[dict[str, Any]]:
    # Tâche sans résultat : une seule ligne, son statut dans label, le reste vide.
    if result["status"] != "done":
        return [{"analysis_id": analysis_id, "task": task, "label": result["status"]}]
    rows = []
    # Étape 1 : probabilités globales, sans segment.
    for rank, entry in enumerate(result["probabilities"], start=1):
        row = _probability_row(analysis_id, task, result, rank, entry)
        row["scope"] = "global"
        rows.append(row)
    # Étape 2 : probabilités de chaque segment ; segments numérotés à partir de 1.
    for segment_index, segment in enumerate(result["segments"], start=1):
        for rank, entry in enumerate(segment["probabilities"], start=1):
            row = _probability_row(analysis_id, task, result, rank, entry)
            row["scope"] = "segment"
            row["segment_index"] = segment_index
            row["start_s"] = segment["start_s"]
            row["end_s"] = segment["end_s"]
            rows.append(row)
    return rows


def _probability_row(
    analysis_id: str, task: str, result: dict[str, Any], rank: int, entry: dict[str, Any]
) -> dict[str, Any]:
    # Colonnes communes aux lignes globales et de segment ; text attend la transcription (C17).
    calibrated = "true" if result["calibrated"] else "false"
    return {
        "analysis_id": analysis_id,
        "task": task,
        "rank": rank,
        "label": entry["label"],
        "label_fr": entry["label_fr"],
        "probability": entry["probability"],
        "model_id": result["model_id"],
        "model_version": result["model_version"],
        "calibrated": calibrated,
        "text": "",
    }


def _pdf_styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "title": sample["Title"],
        "heading": sample["Heading2"],
        "body": sample["BodyText"],
        "small": ParagraphStyle("small", parent=sample["BodyText"], fontSize=8, leading=10),
        "banner": ParagraphStyle(
            "banner", parent=sample["BodyText"], fontName="Helvetica-Bold", alignment=1
        ),
    }


def _header_flowables(record: AnalysisRecord, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    created_at = record.created_at.strftime("%d/%m/%Y à %H:%M (UTC)")
    duration = _duration_fr(record.duration_s)
    profile = PROFILE_TITLES[record.profile]
    details = f"Date : {created_at} · Durée : {duration} · Profil : {profile}"
    return [
        Paragraph(f"Analyse EchoLens : {_escape(record.original_filename)}", styles["title"]),
        Paragraph(details, styles["body"]),
        Spacer(1, 0.3 * cm),
    ]


def _demo_banner(styles: dict[str, ParagraphStyle]) -> Table:
    banner = Table([[Paragraph(DEMO_BANNER, styles["banner"])]], colWidths=["100%"])
    banner.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.lightgrey),
                ("BOX", (0, 0), (-1, -1), 1, colors.black),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    return banner


def _spectrogram_flowables(path: Path, styles: dict[str, ParagraphStyle]) -> list[Flowable]:
    heading = Paragraph("Spectrogramme log-Mel", styles["heading"])
    if not path.is_file():
        missing = Paragraph("Spectrogramme indisponible pour cette analyse.", styles["body"])
        return [heading, missing]
    width = A4[0] - 2 * PAGE_MARGIN
    image = Image(str(path), width=width, height=SPECTROGRAM_HEIGHT)
    caption = "Temps de gauche à droite, fréquences graves en bas, aigus en haut."
    return [heading, image, Paragraph(caption, styles["small"])]


def _task_flowables(
    task: str, result: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> list[Flowable]:
    flowables: list[Flowable] = [Paragraph(TASK_TITLES[task], styles["heading"])]
    # Tâche sans résultat : son message (« Aucune parole détectée »…), puis le modèle.
    if result["status"] != "done":
        flowables.append(Paragraph(f"Statut : {result['message']}", styles["body"]))
        flowables.append(Paragraph(_model_line(result), styles["small"]))
        return flowables
    # Étape 1 : statut et les 3 classes les plus probables (liste déjà triée par l'API).
    flowables.append(Paragraph("Statut : terminé", styles["body"]))
    flowables.append(_top_classes_table(result))
    # Étape 2 : les segments dans l'ordre du temps, puis le modèle.
    flowables.append(Spacer(1, 0.2 * cm))
    flowables.extend(_segments_flowables(result, styles))
    flowables.append(Paragraph(_model_line(result), styles["small"]))
    return flowables


def _top_classes_table(result: dict[str, Any]) -> Table:
    rows = [["Rang", "Classe", "Probabilité"]]
    top_classes = result["probabilities"][:TOP_CLASS_COUNT]
    for rank, entry in enumerate(top_classes, start=1):
        rows.append([str(rank), entry["label_fr"], _percent_fr(entry["probability"])])
    return _simple_table(rows)


def _segments_flowables(
    result: dict[str, Any], styles: dict[str, ParagraphStyle]
) -> list[Flowable]:
    segments = result["segments"]
    rows = [["Début", "Fin", "Classe"]]
    for segment in segments[:MAX_PDF_SEGMENTS]:
        start = _seconds_fr(segment["start_s"])
        end = _seconds_fr(segment["end_s"])
        rows.append([start, end, segment["label_fr"]])
    flowables: list[Flowable] = [_simple_table(rows)]
    # Au-delà de MAX_PDF_SEGMENTS, on renvoie au CSV plutôt que d'allonger le rapport.
    hidden_count = len(segments) - MAX_PDF_SEGMENTS
    if hidden_count > 0:
        note = f"… et {hidden_count} segment(s) de plus, détaillés dans l'export CSV."
        flowables.append(Paragraph(note, styles["small"]))
    return flowables


def _simple_table(rows: list[list[str]]) -> Table:
    table = Table(rows, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.black),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return table


def _model_line(result: dict[str, Any]) -> str:
    if result["model_id"] is None:
        return "Modèle : aucun (tâche pas encore branchée)."
    calibrated = "calibré" if result["calibrated"] else "non calibré"
    return f"Modèle : {result['model_id']} · version {result['model_version']} · {calibrated}"


def _has_demo_result(results: dict[str, Any]) -> bool:
    model_ids = [result["model_id"] for result in results.values()]
    return DEMO_MODEL_ID in model_ids


def _percent_fr(probability: float) -> str:
    # « 58 % », espace insécable avant % ; en dessous de 1 %, on ne montre pas « 0 % ».
    percent = round(probability * 100)
    if percent < 1:
        return "< 1 %"
    return f"{percent} %"


def _seconds_fr(seconds: float) -> str:
    # « 12,5 s » : une décimale, virgule française.
    text = f"{seconds:.1f}".replace(".", ",")
    return f"{text} s"


def _duration_fr(duration_s: float | None) -> str:
    if duration_s is None:
        return "inconnue"
    total = round(duration_s)
    minutes = total // SECONDS_PER_MINUTE
    seconds = total % SECONDS_PER_MINUTE
    if minutes == 0:
        return _seconds_fr(duration_s)
    return f"{minutes} min {seconds} s"


def _escape(text: str) -> str:
    # Paragraph lit un mini-HTML : « & », « < » et « > » d'un nom de fichier doivent être échappés.
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    return text.replace(">", "&gt;")
