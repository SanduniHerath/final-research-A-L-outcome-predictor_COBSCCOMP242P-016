"""Build the expert content-validity form (Phase 1).

Produces one Excel workbook to send to the expert (cover letter, instructions,
ratings sheet with 1-4 drop-downs, expert details) and Markdown copies of the cover
letter and question list for the thesis appendix. The returned workbook is read by
``src.data.cvi``.

    python -m src.data.expert_form
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.worksheet.worksheet import Worksheet

from src.data.cvi import RATINGS_SHEET
from src.utils.config import load_config, resolve_path
from src.utils.logging_setup import get_logger

logger = get_logger(__name__)

SCALES: dict[str, list[str]] = {
    "Relevance": [
        "1 = Not relevant",
        "2 = Somewhat relevant (needs major change)",
        "3 = Quite relevant (needs minor change)",
        "4 = Highly relevant",
    ],
    "Clarity": [
        "1 = Not clear",
        "2 = Needs major revision to be clear",
        "3 = Clear but needs minor revision",
        "4 = Very clear",
    ],
    "Simplicity": [
        "1 = Not simple",
        "2 = Needs major revision to be simple",
        "3 = Simple but needs minor revision",
        "4 = Very simple",
    ],
}

COVER_LETTER = """Dear {expert},

Request to review a research questionnaire (content validity)

I am {researcher}, a final-year undergraduate at {institution}, working under the supervision of {supervisor}. My research builds an AI decision-support tool that helps G.C.E. O/L students in Sri Lanka understand their likely A/L Science-stream outcomes and plan their studies.

The tool is trained on an online questionnaire answered by undergraduates of Sri Lankan state universities who completed the A/L in the Science stream. The questionnaire asks about their background, O/L results, attitudes and study habits during O/L, goals and activities, A/L preparation and A/L outcomes. It is bilingual (English and Sinhala).

The questionnaire has already been used to collect responses. I am asking for your expert review so that its content validity can be documented and the questionnaire improved for future use.

What I am asking you to do (about 20 to 30 minutes):
1. Read the "Instructions" sheet.
2. In the "Ratings" sheet, rate each of the {n_items} questions from 1 to 4 for relevance, clarity and simplicity, using the drop-down in each cell.
3. Add a comment wherever you think a question, its Sinhala wording or its answer options should change.
4. Fill in the "Expert details" sheet and return the file to me by {deadline}.

Your ratings will be used only for this research. Your name will not be published without your permission; in the thesis you will be described by your role and experience only.

Thank you very much for your time and expertise.

Yours sincerely,
{researcher}
{contact}
"""

PLACEHOLDERS = {
    "expert": "[Expert's name and title]",
    "researcher": "[Your full name]",
    "institution": "[Your university / institute]",
    "supervisor": "[Supervisor's name and title]",
    "deadline": "[return date]",
    "contact": "[Your email address]",
}

CONSTRUCT_NOTES = [
    "Questions 14-17 measure academic self-efficacy during O/L (adapted from the MSLQ, "
    "Pintrich et al., 1991).",
    "Questions 18-21 measure effort regulation and time management during O/L (adapted from "
    "the MSLQ). Question 21 is negatively worded on purpose.",
    "Questions 22-25 measure interest in and value of Science and Mathematics (developed for "
    "this study).",
    "Other questions are factual (background, grades, activities, outcomes) and are used as "
    "single items, not as scales.",
    "Respondents answer about their own past (O/L and A/L years); they are now undergraduates.",
]

HEADERS = [
    "No",
    "Section",
    "Question (English)",
    "Question (Sinhala)",
    "Answer type",
    "Answer options",
    "Relevance",
    "Clarity",
    "Simplicity",
    "Comments / suggested change",
]
WIDTHS = [5, 26, 48, 48, 14, 48, 11, 11, 11, 40]


def load_items() -> list[dict[str, Any]]:
    """Return the questions listed in ``configs/expert_items.yaml``."""
    return load_config("expert_items")["items"]


def cover_letter(n_items: int) -> str:
    """Return the cover letter text with placeholders left for the researcher to fill."""
    return COVER_LETTER.format(n_items=n_items, **PLACEHOLDERS)


def _write_lines(sheet: Worksheet, lines: list[str], bold_first: bool = False) -> None:
    """Write one line per row in column A with wrapping."""
    sheet.column_dimensions["A"].width = 120
    for row, line in enumerate(lines, start=1):
        cell = sheet.cell(row=row, column=1, value=line)
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        if bold_first and row == 1:
            cell.font = Font(bold=True, size=13)


def instruction_lines() -> list[str]:
    """Return the instruction text shown on the Instructions sheet."""
    lines = [
        "Instructions",
        "",
        "Please rate every question on three aspects, using the drop-down list in each cell:",
        "",
    ]
    for name, levels in SCALES.items():
        lines.append(f"{name}:")
        lines += [f"    {level}" for level in levels]
        lines.append("")
    lines += [
        "Relevance: does the question measure something that matters for the study's purpose?",
        "Clarity: will a respondent understand the question and its options in the same way "
        "the researcher intends (in both English and Sinhala)?",
        "Simplicity: is the question short and easy to answer, without technical words?",
        "",
        "Background to help you judge relevance:",
        *[f"  - {note}" for note in CONSTRUCT_NOTES],
        "",
        "Please use the Comments column for any change you would suggest, including to the "
        "Sinhala wording or the answer options.",
    ]
    return lines


def build_workbook(items: list[dict[str, Any]]) -> Workbook:
    """Create the workbook with Cover letter, Instructions, Ratings and Expert details sheets."""
    book = Workbook()
    letter = book.active
    letter.title = "Cover letter"
    _write_lines(letter, cover_letter(len(items)).splitlines())
    _write_lines(book.create_sheet("Instructions"), instruction_lines(), bold_first=True)

    ratings = book.create_sheet(RATINGS_SHEET)
    thin = Side(style="thin", color="C3C2B7")
    header_fill = PatternFill("solid", fgColor="DCE9F9")
    input_fill = PatternFill("solid", fgColor="FFF8E1")
    for col, (title, width) in enumerate(zip(HEADERS, WIDTHS, strict=True), start=1):
        cell = ratings.cell(row=1, column=col, value=title)
        cell.font = Font(bold=True)
        cell.fill = header_fill
        cell.alignment = Alignment(wrap_text=True, vertical="center")
        ratings.column_dimensions[cell.column_letter].width = width
    validation = DataValidation(type="whole", operator="between", formula1="1", formula2="4")
    validation.error = "Please enter a whole number from 1 to 4."
    validation.prompt = "1 = lowest, 4 = highest (see Instructions)"
    ratings.add_data_validation(validation)
    for row, item in enumerate(items, start=2):
        values = [
            item["no"],
            item["section"],
            item["question_en"],
            item["question_si"],
            item["answer_type"],
            item["options"],
        ]
        for col, value in enumerate(values, start=1):
            cell = ratings.cell(row=row, column=col, value=value)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
            cell.border = Border(bottom=thin)
        for col in (7, 8, 9, 10):
            cell = ratings.cell(row=row, column=col)
            cell.fill = input_fill
            cell.border = Border(top=thin, bottom=thin, left=thin, right=thin)
            cell.alignment = Alignment(wrap_text=True, vertical="top")
        validation.add(f"G{row}:I{row}")
    ratings.freeze_panes = "C2"

    details = book.create_sheet("Expert details")
    fields = [
        "Name (optional in thesis)",
        "Highest qualification",
        "Current position",
        "Area of expertise",
        "Years of experience in education / research",
        "Date of review",
        "General comments on the questionnaire",
    ]
    details.column_dimensions["A"].width = 45
    details.column_dimensions["B"].width = 70
    for row, field in enumerate(fields, start=1):
        details.cell(row=row, column=1, value=field).font = Font(bold=True)
        details.cell(row=row, column=2).fill = input_fill
    return book


def markdown_question_table(items: list[dict[str, Any]]) -> str:
    """Return the question list as a Markdown table for the thesis appendix."""
    lines = [
        "| No | Section | Question (English) | Answer options |",
        "|---|---|---|---|",
    ]
    for item in items:
        options = item["options"].replace("|", "/")
        lines.append(f"| {item['no']} | {item['section']} | {item['question_en']} | {options} |")
    return "\n".join(lines)


def write_markdown(items: list[dict[str, Any]], out_dir: Path) -> None:
    """Write the cover letter and the form (instructions + question table) as Markdown."""
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "cover_letter.md").write_text(
        "# Cover letter - expert content-validity review\n\n"
        + cover_letter(len(items)).replace("\n", "  \n"),
        encoding="utf-8",
    )
    scales = "\n".join(
        f"**{name}:** " + "; ".join(levels) + "\n" for name, levels in SCALES.items()
    )
    notes = "\n".join(f"- {note}" for note in CONSTRUCT_NOTES)
    (out_dir / "expert_validation_form.md").write_text(
        "# Expert content-validity form\n\n"
        "Each question is rated from 1 to 4 for relevance, clarity and simplicity.\n\n"
        f"{scales}\n## Background for the expert\n\n{notes}\n\n"
        f"## Questions\n\n{markdown_question_table(items)}\n",
        encoding="utf-8",
    )


def main() -> int:
    """Write the expert workbook and Markdown copies."""
    items = load_items()
    docs_dir = resolve_path(load_config("project")["paths"]["docs"]) / "phase01_expert_form"
    docs_dir.mkdir(parents=True, exist_ok=True)
    workbook_path = docs_dir / "expert_content_validity_form.xlsx"
    build_workbook(items).save(workbook_path)
    write_markdown(items, docs_dir)
    logger.info("Wrote expert form with %d questions to %s", len(items), docs_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
