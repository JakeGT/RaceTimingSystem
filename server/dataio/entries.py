# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Entry lists in and out as CSV.

Import reads this project's own export and the legacy participant files
(`BibNumber,Firstname,Lastname,Gender,ClubName,TeamName,AgeCategory,Age`). Rows are
matched to existing entries by bib, so importing the same file twice changes nothing
and importing a corrected file updates people in place. If any row has a problem,
nothing is saved and every problem is reported at once.
"""

import re
from collections.abc import Iterable
from datetime import date
from typing import Any
from uuid import UUID

from django.core.exceptions import ValidationError
from django.db import transaction

from dataio.csvfiles import CsvError, ImportReport, parse_bool, read_table, write_csv
from events.categories import pick_category
from events.models import Entry, Event, Gender, Race, Wave
from results.services import rebuild_races

ALIASES: dict[str, tuple[str, ...]] = {
    "bib": ("bib", "bibnumber", "bibno", "racenumber", "number"),
    "given_name": ("givenname", "firstname", "forename", "first"),
    "family_name": ("familyname", "lastname", "surname", "last"),
    "name": ("name", "fullname"),
    "gender": ("gender", "sex"),
    "date_of_birth": ("dateofbirth", "dob", "birthdate", "birthday"),
    "age": ("age", "declaredage"),
    "club": ("club", "clubname"),
    "email": ("email", "emailaddress"),
    "hide_name": ("hidename", "anonymous"),
    "race": ("race", "racename"),
    "wave": ("wave", "wavename"),
}
# Legacy columns with no equivalent: teams aren't modelled yet, and categories are
# worked out from the race's category scheme rather than typed in. `status` is in
# exports for reference, but statuses change through the review tools (audit log).
KNOWN_UNUSED = ("teamname", "team", "agecategory", "oldcategory", "category", "status")

# Field names on Entry that each column fills in.
_FIELDS = {
    "given_name": "given_name",
    "family_name": "family_name",
    "gender": "gender",
    "date_of_birth": "date_of_birth",
    "age": "declared_age",
    "club": "club",
    "email": "email",
    "hide_name": "hide_name",
}

_GENDERS = {
    Gender.MALE: {"m", "male", "man", "men", "boy"},
    Gender.FEMALE: {"f", "w", "female", "woman", "women", "girl"},
    # Legacy files used "other"; it's the closest match to the non-binary categories.
    Gender.NON_BINARY: {"x", "nb", "nonbinary", "other"},
    Gender.UNDISCLOSED: {"", "u", "unknown", "undisclosed", "prefernottosay", "none"},
}
_GENDER_LOOKUP = {spelling: g for g, spellings in _GENDERS.items() for spelling in spellings}


def parse_gender(text: str) -> str:
    gender = _GENDER_LOOKUP.get(re.sub(r"[^a-z]", "", text.lower()))
    if gender is None:
        raise ValueError(f"{text!r} isn't a gender this system knows (male, female, non-binary).")
    return str(gender)


def parse_date(text: str) -> date | None:
    """ISO (2001-04-30) or day first (30/04/2001), as UK spreadsheets write it."""
    text = text.strip()
    if not text:
        return None
    if match := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", text):
        year, month, day = match.groups()
    elif match := re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", text):
        day, month, year = match.groups()
    else:
        raise ValueError(f"{text!r} isn't a date like 2001-04-30 or 30/04/2001.")
    try:
        return date(int(year), int(month), int(day))
    except ValueError:
        raise ValueError(f"{text!r} isn't a real date.") from None


def _parse_age(text: str) -> int | None:
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        raise ValueError(f"Age {text!r} isn't a whole number.") from None


_PARSERS: dict[str, Any] = {
    "gender": parse_gender,
    "date_of_birth": parse_date,
    "age": _parse_age,
    "hide_name": parse_bool,
}


class _Races:
    """Finds races and waves by name (case doesn't matter) for one event."""

    def __init__(self, event: Event, default: Race | None) -> None:
        self.races = {r.name.casefold(): r for r in event.races.all()}
        self.waves: dict[UUID, dict[str, Wave]] = {}
        for wave in Wave.objects.filter(event=event):
            self.waves.setdefault(wave.race_id, {})[wave.name.casefold()] = wave
        self.default = default or (
            next(iter(self.races.values())) if len(self.races) == 1 else None
        )

    def race(self, name: str) -> Race:
        if not name:
            if self.default is None:
                raise ValueError(
                    "Say which race: this event has several, and there's no race column."
                )
            return self.default
        race = self.races.get(name.casefold())
        if race is None:
            known = ", ".join(sorted(r.name for r in self.races.values())) or "none yet"
            raise ValueError(f"There's no race called {name!r} (races: {known}).")
        return race

    def wave(self, race: Race, name: str) -> Wave | None:
        waves = self.waves.get(race.pk, {})
        if not name:
            if len(waves) > 1:
                raise ValueError(f"{race.name} has several waves, so say which one.")
            return None
        wave = waves.get(name.casefold())
        if wave is None:
            raise ValueError(f"{race.name} has no wave called {name!r}.")
        return wave


def import_entries(
    event: Event, data: bytes, *, race: Race | None = None, dry_run: bool = False
) -> ImportReport:
    """Create or update entries from a CSV. `race` is used for rows without a race column."""
    report = ImportReport(dry_run=dry_run)
    if race is not None and race.event_id != event.pk:
        raise CsvError("That race belongs to another event.")
    table = read_table(data, ALIASES, known_unused=KNOWN_UNUSED)
    report.ignored_columns = table.ignored
    if "bib" not in table.columns:
        raise CsvError("There's no bib column (e.g. Bib or BibNumber).")
    if not {"given_name", "name"} & table.columns.keys():
        raise CsvError("There's no name column (e.g. Firstname, or Name).")

    lookup = _Races(event, race)
    existing = {e.bib: e for e in Entry.objects.filter(event=event).select_related("wave")}
    seen: dict[str, int] = {}
    to_create: list[Entry] = []
    to_update: list[Entry] = []
    touched_races: set[UUID] = set()

    for line, row in table.rows:
        bib = row["bib"]
        if not bib:
            report.error(line, "No bib.")
            continue
        if bib in seen:
            report.error(line, f"Bib {bib} is also on line {seen[bib]}.")
            continue
        seen[bib] = line
        entry = existing.get(bib)
        before = _snapshot(entry) if entry else None
        try:
            values = _values(row)
            entry_race = lookup.race(row.get("race", ""))
            # Without a wave column, keep the entry's wave unless it moved race.
            keep_wave = (
                "wave" not in row
                and entry is not None
                and entry.wave is not None
                and entry.wave.race_id == entry_race.pk
            )
            wave = (
                entry.wave if keep_wave and entry else lookup.wave(entry_race, row.get("wave", ""))
            )
        except ValueError as e:
            report.error(line, str(e))
            continue

        if entry is None:
            entry = Entry(event=event, bib=bib)
        elif entry.race_id != entry_race.pk:
            touched_races.add(entry.race_id)
        entry.race, entry.wave = entry_race, wave
        for name, value in values.items():
            setattr(entry, name, value)
        try:
            entry.full_clean(exclude=["event"], validate_unique=False, validate_constraints=False)
        except ValidationError as e:
            report.error(line, _describe(e))
            continue

        if before is None:
            to_create.append(entry)
        elif _snapshot(entry) != before:
            to_update.append(entry)
        else:
            report.unchanged += 1
            continue
        touched_races.add(entry_race.pk)

    report.created, report.updated = len(to_create), len(to_update)
    if report.errors or dry_run:
        return report
    with transaction.atomic():
        Entry.objects.bulk_create(to_create)
        Entry.objects.bulk_update(to_update, [*_FIELDS.values(), "race", "wave"])
        rebuild_races(Race.objects.filter(pk__in=touched_races))
    return report


def _values(row: dict[str, str]) -> dict[str, Any]:
    """Model field values for the columns this file has."""
    values: dict[str, Any] = {}
    if "name" in row and "given_name" not in row:
        values["given_name"], values["family_name"] = row["name"], ""
    for column, field in _FIELDS.items():
        if column in row:
            parse = _PARSERS.get(column)
            values[field] = parse(row[column]) if parse else row[column]
    return values


def _snapshot(entry: Entry) -> tuple[Any, ...]:
    return (entry.race_id, entry.wave_id, *(getattr(entry, f) for f in _FIELDS.values()))


def _describe(error: ValidationError) -> str:
    if hasattr(error, "error_dict"):
        return " ".join(
            f"{name.replace('_', ' ').capitalize()}: {' '.join(messages)}"
            if name != "__all__"
            else " ".join(messages)
            for name, messages in error.message_dict.items()
        )
    return " ".join(error.messages)


# ---------------------------------------------------------------------------- export

NATIVE_HEADER = (
    "bib",
    "given_name",
    "family_name",
    "gender",
    "date_of_birth",
    "age",
    "club",
    "email",
    "hide_name",
    "race",
    "wave",
    "status",
)
LEGACY_HEADER = (
    "BibNumber",
    "Firstname",
    "Lastname",
    "Gender",
    "ClubName",
    "TeamName",
    "AgeCategory",
    "Age",
)
_LEGACY_GENDER = {Gender.MALE: "male", Gender.FEMALE: "female", Gender.NON_BINARY: "other"}


def _ordered(event: Event, race: Race | None) -> Iterable[Entry]:
    entries = Entry.objects.filter(event=event).select_related(
        "race__event", "race__category_scheme", "wave"
    )
    if race is not None:
        entries = entries.filter(race=race)
    return sorted(entries, key=lambda e: (e.race.order, e.race.name, _bib_key(e.bib)))


def _bib_key(bib: str) -> tuple[int, int | str]:
    return (0, int(bib)) if bib.isdigit() else (1, bib)


def export_entries(event: Event, *, race: Race | None = None, legacy: bool = False) -> str:
    """The entry list as CSV. The native format imports back unchanged; the legacy one
    matches the old system's participant upload."""
    entries = _ordered(event, race)
    if legacy:
        bands: dict[UUID, Any] = {}
        rows = []
        for e in entries:
            if e.race_id not in bands:
                scheme = e.race.category_scheme
                bands[e.race_id] = scheme.bands() if scheme else None
            age = e.age_for_categories()
            band = pick_category(bands[e.race_id], e.gender, age) if bands[e.race_id] else None
            rows.append(
                (
                    e.bib,
                    e.given_name,
                    e.family_name,
                    _LEGACY_GENDER.get(Gender(e.gender), ""),
                    e.club,
                    "",
                    band.code if band else "",
                    "" if age is None else age,
                )
            )
        return write_csv(LEGACY_HEADER, rows)
    return write_csv(
        NATIVE_HEADER,
        (
            (
                e.bib,
                e.given_name,
                e.family_name,
                e.gender,
                e.date_of_birth.isoformat() if e.date_of_birth else "",
                "" if e.declared_age is None else e.declared_age,
                e.club,
                e.email,
                "yes" if e.hide_name else "no",
                e.race.name,
                e.wave.name if e.wave else "",
                e.status,
            )
            for e in entries
        ),
    )
