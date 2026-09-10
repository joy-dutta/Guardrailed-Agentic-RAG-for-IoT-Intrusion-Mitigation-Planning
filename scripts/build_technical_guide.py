"""Build the public technical reproducibility guide as a styled PDF."""

from __future__ import annotations

import argparse
import html
import re
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    ListFlowable,
    ListItem,
    PageBreak,
    PageTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus.tableofcontents import TableOfContents


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "docs" / "technical" / "REPRODUCIBILITY_GUIDE.md"
OUTPUT = ROOT / "docs" / "technical" / "Technical_Reproducibility_Guide.pdf"
ACCENT = colors.HexColor("#176B67")
DARK = colors.HexColor("#263238")
LIGHT = colors.HexColor("#E8F2F1")
RULE = colors.HexColor("#B8C7C6")


class GuideDocument(BaseDocTemplate):
    def __init__(self, filename: str) -> None:
        super().__init__(
            filename,
            pagesize=A4,
            leftMargin=19 * mm,
            rightMargin=19 * mm,
            topMargin=19 * mm,
            bottomMargin=18 * mm,
            title="Technical Reproducibility Guide",
            author=(
                "Joy Dutta, Hossien B. Eldeeb, Samara Mayhoub, "
                "Ali Ismail Awad, Ezedin Barka, Hassnaa Moustafa"
            ),
        )
        frame = Frame(
            self.leftMargin,
            self.bottomMargin,
            self.width,
            self.height,
            id="content",
        )
        self.addPageTemplates(
            [PageTemplate(id="main", frames=[frame], onPage=draw_header_footer)]
        )

    def afterFlowable(self, flowable) -> None:  # noqa: N802
        if isinstance(flowable, Paragraph):
            level = getattr(flowable, "toc_level", None)
            if level is not None:
                text = flowable.getPlainText()
                key = f"heading-{self.seq.nextf('heading')}"
                self.canv.bookmarkPage(key)
                self.canv.addOutlineEntry(text, key, level=level, closed=False)
                self.notify("TOCEntry", (level, text, self.page, key))


def draw_header_footer(canvas, doc) -> None:
    canvas.saveState()
    if doc.page > 1:
        canvas.setStrokeColor(RULE)
        canvas.line(doc.leftMargin, A4[1] - 13 * mm, A4[0] - doc.rightMargin, A4[1] - 13 * mm)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#536866"))
        canvas.drawString(doc.leftMargin, A4[1] - 10 * mm, "Technical Reproducibility Guide")
        canvas.drawRightString(A4[0] - doc.rightMargin, 10 * mm, str(doc.page))
    canvas.restoreState()


def styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "CoverTitle",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=25,
            leading=30,
            textColor=DARK,
            alignment=TA_LEFT,
            spaceAfter=8 * mm,
        ),
        "subtitle": ParagraphStyle(
            "CoverSubtitle",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=12,
            leading=17,
            textColor=ACCENT,
            spaceAfter=5 * mm,
        ),
        "meta": ParagraphStyle(
            "Meta",
            parent=base["Normal"],
            fontSize=9,
            leading=13,
            textColor=colors.HexColor("#536866"),
        ),
        "h1": ParagraphStyle(
            "Heading1Custom",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=16,
            leading=20,
            textColor=ACCENT,
            spaceBefore=7 * mm,
            spaceAfter=3 * mm,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "Heading2Custom",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=DARK,
            spaceBefore=5 * mm,
            spaceAfter=2 * mm,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "BodyCustom",
            parent=base["BodyText"],
            fontName="Helvetica",
            fontSize=9.3,
            leading=13.2,
            textColor=DARK,
            spaceAfter=2.4 * mm,
        ),
        "bullet": ParagraphStyle(
            "BulletCustom",
            parent=base["BodyText"],
            fontSize=9.1,
            leading=12.8,
            textColor=DARK,
        ),
        "code": ParagraphStyle(
            "CodeCustom",
            parent=base["Code"],
            fontName="Courier",
            fontSize=7.8,
            leading=10.5,
            leftIndent=4 * mm,
            rightIndent=4 * mm,
            borderColor=RULE,
            borderWidth=0.5,
            borderPadding=3 * mm,
            backColor=colors.HexColor("#F5F7F7"),
            spaceBefore=1.5 * mm,
            spaceAfter=3 * mm,
        ),
        "table": ParagraphStyle(
            "TableText",
            parent=base["BodyText"],
            fontSize=7.5,
            leading=9.6,
            textColor=DARK,
        ),
        "toc_title": ParagraphStyle(
            "TOCTitle",
            parent=base["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=18,
            textColor=ACCENT,
            spaceAfter=5 * mm,
        ),
    }


def inline_markup(text: str) -> str:
    value = html.escape(text.strip())
    value = re.sub(r"`([^`]+)`", r'<font name="Courier">\1</font>', value)
    value = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", value)
    value = re.sub(r"\[([^]]+)\]\(([^)]+)\)", r'<link href="\2" color="#176B67">\1</link>', value)
    return value


def make_table(lines: list[str], style: ParagraphStyle, available_width: float) -> Table:
    rows: list[list[Paragraph]] = []
    for index, line in enumerate(lines):
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if index == 1 and all(re.fullmatch(r":?-{3,}:?", cell) for cell in cells):
            continue
        if index == 0:
            rows.append(
                [
                    Paragraph(
                        f'<font color="#FFFFFF"><b>{inline_markup(cell)}</b></font>',
                        style,
                    )
                    for cell in cells
                ]
            )
        else:
            rows.append([Paragraph(inline_markup(cell), style) for cell in cells])
    columns = max(len(row) for row in rows)
    widths = [available_width / columns] * columns
    table = Table(rows, colWidths=widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("GRID", (0, 0), (-1, -1), 0.35, RULE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


def markdown_flowables(text: str, doc: GuideDocument, style: dict[str, ParagraphStyle]):
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("## 1. Purpose"))
    lines = lines[start:]
    story = []
    paragraph: list[str] = []
    bullets: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            story.append(Paragraph(inline_markup(" ".join(paragraph)), style["body"]))
            paragraph.clear()

    def flush_bullets() -> None:
        if bullets:
            story.append(
                ListFlowable(
                    [ListItem(Paragraph(inline_markup(item), style["bullet"])) for item in bullets],
                    bulletType="bullet",
                    leftIndent=5 * mm,
                    bulletFontName="Helvetica",
                    bulletFontSize=6,
                    spaceAfter=2 * mm,
                )
            )
            bullets.clear()

    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line:
            flush_paragraph()
            flush_bullets()
            index += 1
            continue
        if line.startswith("```"):
            flush_paragraph()
            flush_bullets()
            language = line[3:].strip()
            code_lines = []
            index += 1
            while index < len(lines) and not lines[index].startswith("```"):
                code_lines.append(lines[index])
                index += 1
            label = f"[{language}]\n" if language else ""
            code = html.escape(label + "\n".join(code_lines)).replace("\n", "<br/>")
            story.append(Paragraph(code, style["code"]))
            index += 1
            continue
        if line.startswith("|"):
            flush_paragraph()
            flush_bullets()
            table_lines = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                table_lines.append(lines[index])
                index += 1
            story.append(make_table(table_lines, style["table"], doc.width))
            story.append(Spacer(1, 3 * mm))
            continue
        heading = re.match(r"^(#{2,3})\s+(.+)$", line)
        if heading:
            flush_paragraph()
            flush_bullets()
            level = len(heading.group(1)) - 2
            para = Paragraph(inline_markup(heading.group(2)), style["h1" if level == 0 else "h2"])
            para.toc_level = level
            story.append(para)
            index += 1
            continue
        if line.startswith("- "):
            flush_paragraph()
            bullets.append(line[2:].strip())
            index += 1
            continue
        numbered = re.match(r"^\d+\.\s+(.+)$", line)
        if numbered:
            flush_paragraph()
            flush_bullets()
            story.append(
                Paragraph(
                    inline_markup(line),
                    ParagraphStyle(
                        "NumberedInline",
                        parent=style["body"],
                        leftIndent=5 * mm,
                        firstLineIndent=-5 * mm,
                    ),
                )
            )
            index += 1
            continue
        if line.startswith("> "):
            flush_paragraph()
            flush_bullets()
            story.append(
                Paragraph(
                    f"<i>{inline_markup(line[2:])}</i>",
                    ParagraphStyle(
                        "Quote",
                        parent=style["body"],
                        leftIndent=5 * mm,
                        borderColor=ACCENT,
                        borderWidth=0,
                        borderPadding=2 * mm,
                    ),
                )
            )
            index += 1
            continue
        paragraph.append(line.strip())
        index += 1
    flush_paragraph()
    flush_bullets()
    return story


def build(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    style = styles()
    doc = GuideDocument(str(output))
    story = [
        Spacer(1, 10 * mm),
        Paragraph("TECHNICAL REPRODUCIBILITY GUIDE", style["subtitle"]),
        Paragraph(
            "Confidence-Aware Guardrailed Agentic RAG for IoT Intrusion Mitigation Planning",
            style["title"],
        ),
        Paragraph(
            "Open reproducibility package",
            style["subtitle"],
        ),
        Spacer(1, 2 * mm),
        Paragraph(
            "Joy Dutta, Hossien B. Eldeeb, Samara Mayhoub, Ali Ismail Awad, "
            "Ezedin Barka, and Hassnaa Moustafa<br/>"
            "Artifact version 1.1.0 | 10 September 2026",
            style["meta"],
        ),
        Spacer(1, 12 * mm),
    ]
    story.extend(
        [
            Paragraph(
                "A self-contained handover from CICIoT2023 traffic observations to "
                "source-traceable, deterministically bounded mitigation intent. The "
                "prototype is offline and does not execute network actions.",
                style["body"],
            ),
            PageBreak(),
            Paragraph("Contents", style["toc_title"]),
        ]
    )
    toc = TableOfContents()
    toc.levelStyles = [
        ParagraphStyle(
            "TOCLevel1",
            fontName="Helvetica",
            fontSize=9,
            leading=13,
            leftIndent=0,
            firstLineIndent=0,
            textColor=DARK,
        ),
        ParagraphStyle(
            "TOCLevel2",
            fontName="Helvetica",
            fontSize=8,
            leading=11,
            leftIndent=8 * mm,
            firstLineIndent=0,
            textColor=colors.HexColor("#536866"),
        ),
    ]
    story.extend([toc, PageBreak()])
    story.extend(markdown_flowables(source.read_text(encoding="utf-8"), doc, style))
    doc.multiBuild(story)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    build(args.source, args.output)
    print(f"Created {args.output}")


if __name__ == "__main__":
    main()
