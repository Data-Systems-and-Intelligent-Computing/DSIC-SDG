from __future__ import annotations

import re
import subprocess
from decimal import Decimal
from pathlib import Path
from typing import Any

from .geography import PROVINCE_KEYS, normalise_name


# The appendix pages carry a diagonal "https://www.bps.go.id" watermark that
# pdftotext interleaves with the table body, either as its own line or as a
# short token wedged between two numeric columns.
WATERMARK_LINE = re.compile(r"^[\s.]*(ht|tp|s:|//w|w|\.b|ps|\.go|\.id|o\.|\.g|id|go|b|s)[\s.]*$")
WATERMARK_INLINE = re.compile(r"(?<=\s)(ht|tp|s:|//w|w|\.b|ps|\.go|\.id|o\.|\.g|id|go)(?=\s)")
# "–" marks a province that did not exist yet and "…" a value that is withheld.
CELL = re.compile(r"-?\d[\d.]*,\d+|-?\d[\d.]*|[–—]|…|\.\.\.|\bNA\b")
COLUMN_HEADER = re.compile(r"\((\d+)\)")
# An indicator code has three dotted groups ("4.1.2*"), which a thousands
# separator such as "16.478" can never produce.
FOOTNOTE_START = re.compile(r"^(Catatan|Sumber|Data|Lanjutan|Lampiran)\b|^\d+\.\d+\.\d+")
MISSING = {"–", "—", "…", "...", "NA"}


def extract_pages(pdf_path: Path) -> list[str]:
    """Render the publication to layout-preserving text, one entry per page."""
    result = subprocess.run(
        ["pdftotext", "-layout", str(pdf_path), "-"],
        capture_output=True,
        check=True,
    )
    return result.stdout.decode("utf-8", errors="replace").split("\f")


def _clean(page: str) -> list[str]:
    lines = []
    for line in page.split("\n"):
        if not line.strip() or WATERMARK_LINE.match(line.strip()):
            continue
        lines.append(WATERMARK_INLINE.sub(" ", line))
    return lines


def _column_numbers(lines: list[str]) -> tuple[int, list[str]] | tuple[None, None]:
    for index, line in enumerate(lines):
        numbers = COLUMN_HEADER.findall(line)
        if len(numbers) >= 3 and numbers[0] == "1":
            return index, numbers[1:]
    return None, None


def parse_page(page: str) -> dict[str, Any] | None:
    """Read one appendix page into `{column number: {province key: token}}`.

    Column 1 is the province name, so the remaining printed column numbers give
    the exact cell count each row must yield. A row that does not produce that
    many tokens is reported rather than guessed at.
    """
    lines = _clean(page)
    header_index, columns = _column_numbers(lines)
    if header_index is None:
        return None

    rows: dict[str, list[str]] = {}
    order: list[str] = []
    current: str | None = None
    buffer: list[str] = []
    for line in lines[header_index + 1 :]:
        text = line.strip()
        label = re.match(r"^([A-Za-z][A-Za-z.\s]*?)(?=\s{2,}|\s*[-\d–…]|$)", text)
        name = label.group(1).strip() if label else ""
        if name and normalise_name(name) in PROVINCE_KEYS and not FOOTNOTE_START.match(text):
            key = normalise_name(name)
            if current is not None:
                rows[current] = buffer
            current, buffer = key, CELL.findall(text[len(name) :])
            order.append(key)
        elif FOOTNOTE_START.match(text):
            if current is not None:
                rows[current] = buffer
            current = None
        elif current is not None:
            buffer.extend(CELL.findall(text))
    if current is not None:
        rows[current] = buffer

    complete = {key: values for key, values in rows.items() if len(values) == len(columns)}
    incomplete = {key: len(values) for key, values in rows.items() if len(values) != len(columns)}
    incomplete.update({key: 0 for key in PROVINCE_KEYS if key not in rows})
    return {
        "columns": columns,
        "rows": complete,
        "incomplete_rows": incomplete,
        "row_order": [key for key in order if key in complete],
    }


def _decimals(token: str) -> int:
    return len(token.split(",")[1]) if "," in token else 0


def read_column(parsed: dict[str, Any], column: str) -> dict[str, dict[str, str]]:
    """Return one printed column as `{province key: {value, note}}`.

    Footnote markers are printed as superscripts that pdftotext glues onto the
    number, so `0,12` with marker 1 arrives as `0,121`. The column's own modal
    decimal count separates the value from the marker; nothing is dropped
    silently, the marker is carried on the cell.
    """
    index = parsed["columns"].index(column)
    raw = {key: values[index] for key, values in parsed["rows"].items()}
    counts: dict[int, int] = {}
    for token in raw.values():
        if token not in MISSING:
            counts[_decimals(token)] = counts.get(_decimals(token), 0) + 1
    modal = max(counts, key=lambda size: (counts[size], -size)) if counts else 0

    cells: dict[str, dict[str, str]] = {}
    for key, token in raw.items():
        if token in MISSING:
            cells[key] = {"value": "", "note": "not_published"}
            continue
        note = ""
        if _decimals(token) > modal:
            whole, fraction = token.split(",")
            token, note = f"{whole},{fraction[:modal]}", f"footnote_{fraction[modal:]}"
        cells[key] = {"value": str(Decimal(token.replace(".", "").replace(",", "."))), "note": note}
    return cells
