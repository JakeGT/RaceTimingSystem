# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Reading and writing the CSV files organisers bring from spreadsheets and entry sites.

Files come from Excel as often as anywhere else, so reading tolerates a byte-order mark,
Windows-1252, semicolons (European Excel) and loose header spellings ("First name",
"FirstName", "first_name" are all the same column).
"""

import csv
import io
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

MAX_ROWS = 20_000

# Spreadsheet apps run cells that start with these as formulas ("CSV injection").
_FORMULA_START = ("=", "+", "-", "@", "\t", "\r")


class CsvError(ValueError):
    """The file as a whole can't be used (not a CSV, no header, missing columns)."""


@dataclass
class RowError:
    line: int  # line in the file, counting the header as line 1
    message: str


@dataclass
class ImportReport:
    """What an import did, or would do on a dry run. Nothing is saved if there are errors."""

    dry_run: bool = False
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[RowError] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    ignored_columns: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def error(self, line: int, message: str) -> None:
        self.errors.append(RowError(line, message))

    def summary(self) -> str:
        if self.errors:
            return f"Nothing imported: {len(self.errors)} row(s) need fixing."
        verb = "Would import" if self.dry_run else "Imported"
        parts = [f"{self.created} new"]
        if self.updated:
            parts.append(f"{self.updated} updated")
        if self.unchanged:
            parts.append(f"{self.unchanged} unchanged")
        if self.skipped:
            parts.append(f"{self.skipped} skipped")
        return f"{verb}: {', '.join(parts)}."


def normalise_header(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


def decode(data: bytes) -> str:
    """UTF-8 (with or without Excel's byte-order mark), else Windows-1252."""
    try:
        return data.decode("utf-8-sig")
    except UnicodeDecodeError:
        return data.decode("cp1252", errors="replace")


@dataclass
class Table:
    columns: dict[str, str]  # canonical name -> header as written in the file
    ignored: list[str]
    rows: list[tuple[int, dict[str, str]]]  # (line number, canonical name -> cell)


def read_table(
    data: bytes,
    aliases: Mapping[str, Iterable[str]],
    *,
    known_unused: Iterable[str] = (),
) -> Table:
    """Parse a CSV into rows keyed by canonical column name.

    `aliases` maps each canonical name to the header spellings that mean it (already
    normalised). Columns not in `aliases` are listed in `ignored`, except `known_unused`,
    which are expected and silently dropped (legacy columns with no new equivalent).
    """
    text = decode(data)
    if not text.strip():
        raise CsvError("The file is empty.")
    first_line = text.split("\n", 1)[0]
    delimiter = max(",;\t", key=first_line.count) if any(d in first_line for d in ",;\t") else ","
    reader = csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)
    header = next(reader, None)
    if not header:
        raise CsvError("The file has no header row.")

    lookup = {alias: canonical for canonical, names in aliases.items() for alias in names}
    unused = set(known_unused)
    columns: dict[str, str] = {}
    positions: dict[str, int] = {}
    ignored: list[str] = []
    for index, raw in enumerate(header):
        key = normalise_header(raw)
        canonical = lookup.get(key)
        if canonical is None:
            if raw.strip() and key not in unused:
                ignored.append(raw.strip())
            continue
        if canonical in columns:
            raise CsvError(
                f"Columns {columns[canonical]!r} and {raw.strip()!r} mean the same thing."
            )
        columns[canonical] = raw.strip()
        positions[canonical] = index

    rows: list[tuple[int, dict[str, str]]] = []
    for cells in reader:
        if not any(cell.strip() for cell in cells):
            continue
        if len(rows) >= MAX_ROWS:
            raise CsvError(f"The file has more than {MAX_ROWS} rows. Split it up.")
        row = {
            name: _unescape(cells[i].strip()) if i < len(cells) else ""
            for name, i in positions.items()
        }
        rows.append((reader.line_num, row))
    return Table(columns=columns, ignored=ignored, rows=rows)


def _unescape(cell: str) -> str:
    """Undo `safe_cell`, so exported files import again unchanged."""
    if len(cell) > 1 and cell[0] == "'" and cell[1] in _FORMULA_START:
        return cell[1:]
    return cell


def safe_cell(value: Any) -> Any:
    """Stop spreadsheet apps running a cell as a formula. Only strings can be one."""
    if isinstance(value, str) and value.startswith(_FORMULA_START):
        return "'" + value
    return value


def write_csv(header: Sequence[str], rows: Iterable[Sequence[Any]]) -> str:
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\r\n")
    writer.writerow(header)
    for row in rows:
        writer.writerow([safe_cell(v) for v in row])
    return out.getvalue()


# ----------------------------------------------------------------------------- times

_DURATION = re.compile(r"^(?:(?:(\d+):)?(\d{1,2}):)?(\d{1,2}(?:[.,]\d+)?)$")


def parse_duration(text: str) -> timedelta:
    """`1:02:03.4`, `02:03`, `45.6` (seconds), with a dot or comma before fractions."""
    match = _DURATION.match(text.strip())
    if not match:
        raise ValueError(f"{text!r} isn't a time like 1:02:03 or 42:15.3.")
    hours, minutes, seconds = match.groups()
    if hours is not None and int(minutes) >= 60:
        raise ValueError(f"{text!r} has more than 59 minutes.")
    whole = float(seconds.replace(",", "."))
    if minutes is not None and whole >= 60:
        raise ValueError(f"{text!r} has more than 59 seconds.")
    return timedelta(hours=int(hours or 0), minutes=int(minutes or 0), seconds=whole)


def format_duration(
    value: timedelta | None, *, decimals: int = 0, two_digit_hours: bool = False
) -> str:
    """`H:MM:SS` (or with `decimals` digits of a second), truncated, never rounded up:
    a runner's time never gets better by being displayed."""
    if value is None:
        return ""
    unit = 10**decimals
    ticks = (value // timedelta(microseconds=1)) * unit // 1_000_000
    whole, fraction = divmod(ticks, unit)
    hours, rest = divmod(whole, 3600)
    minutes, seconds = divmod(rest, 60)
    text = (
        f"{hours:02}:{minutes:02}:{seconds:02}"
        if two_digit_hours
        else f"{hours}:{minutes:02}:{seconds:02}"
    )
    return f"{text}.{fraction:0{decimals}}" if decimals else text


def parse_bool(text: str) -> bool:
    value = text.strip().lower()
    if value in {"", "0", "n", "no", "false", "f"}:
        return False
    if value in {"1", "y", "yes", "true", "t", "x"}:
        return True
    raise ValueError(f"{text!r} isn't yes or no.")
