# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Staff API for getting data in and out: entry lists, times, results and bundles.

Who can do what: anyone on the team can download results (they get published
anyway); entry lists hold personal details, so they and imports need an organiser;
importing a bundle can replace a whole event, so it needs an owner.
"""

import tempfile
from typing import Any
from uuid import UUID

from django.http import FileResponse, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404
from ninja import File, Form, Router, Schema, Status
from ninja.errors import HttpError
from ninja.files import UploadedFile

from accounts.api import Error
from accounts.models import Organisation, Role
from accounts.permissions import STAFF_AUTH, current_user, require_role
from dataio.bundle import BundleError, bundle_filename, export_bundle, import_bundle
from dataio.csvfiles import CsvError, ImportReport
from dataio.entries import export_entries, import_entries
from dataio.results_csv import export_results
from dataio.times import import_times
from events.models import Event, Race, TimingPoint
from timing.review import Actor

MAX_CSV_BYTES = 10 * 1024 * 1024

router = Router(tags=["staff"], auth=STAFF_AUTH)
organisations_router = Router(tags=["staff"], auth=STAFF_AUTH)

_CSV = {200: {"description": "CSV file", "content": {"text/csv": {}}}}
_ZIP = {200: {"description": "Event bundle", "content": {"application/zip": {}}}}


class RowErrorOut(Schema):
    line: int
    message: str


class ImportReportOut(Schema):
    summary: str
    dry_run: bool
    created: int
    updated: int
    unchanged: int
    skipped: int
    errors: list[RowErrorOut]
    warnings: list[str]
    ignored_columns: list[str]


class BundleImportOut(Schema):
    summary: str
    event_id: UUID
    slug: str
    replaced: bool
    rows: dict[str, int]
    crops: int
    warnings: list[str]


def _event(request: HttpRequest, event_id: UUID, minimum: Role) -> Event:
    event = get_object_or_404(Event.objects.select_related("organisation"), pk=event_id)
    require_role(request, event.organisation, minimum)
    return event


def _race(event: Event, race_id: UUID | None) -> Race | None:
    if race_id is None:
        return None
    race = Race.objects.filter(pk=race_id, event=event).first()
    if race is None:
        raise HttpError(400, "That race isn't part of this event.")
    return race


def _read(file: UploadedFile) -> bytes:
    if file.size is not None and file.size > MAX_CSV_BYTES:
        raise HttpError(400, "That file is too big for a CSV (the limit is 10 MB).")
    return bytes(file.read())


def _report(report: ImportReport) -> Status[ImportReportOut]:
    body = ImportReportOut(
        summary=report.summary(),
        dry_run=report.dry_run,
        created=report.created,
        updated=report.updated,
        unchanged=report.unchanged,
        skipped=report.skipped,
        errors=[RowErrorOut(line=e.line, message=e.message) for e in report.errors],
        warnings=report.warnings,
        ignored_columns=report.ignored_columns,
    )
    return Status(200 if report.ok else 422, body)


def bundle_download(event: Event) -> FileResponse:
    # Bundles with crops can be large, so spool to disk. FileResponse closes the file.
    spool = tempfile.TemporaryFile()  # noqa: SIM115
    export_bundle(event, spool)
    spool.seek(0)
    return FileResponse(
        spool, as_attachment=True, filename=bundle_filename(event), content_type="application/zip"
    )


def _download(content: str | bytes, filename: str, content_type: str) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


IMPORT_RESPONSES: dict[int, Any] = {
    200: ImportReportOut,
    422: ImportReportOut,
    400: Error,
    403: Error,
    404: Error,
}


@router.post(
    "/{event_id}/entries/import",
    response=IMPORT_RESPONSES,
    summary="Create or update entries from a CSV (this system's or the legacy format)",
    description=(
        "Rows are matched to entries by bib. If any row has a problem nothing is saved, "
        "and the response (422) lists every problem by line. `dry_run` checks the file "
        "without saving."
    ),
)
def import_entries_csv(
    request: HttpRequest,
    event_id: UUID,
    file: File[UploadedFile],
    race_id: Form[UUID | None] = None,
    dry_run: Form[bool] = False,
) -> Status[ImportReportOut]:
    event = _event(request, event_id, Role.ORGANISER)
    try:
        report = import_entries(event, _read(file), race=_race(event, race_id), dry_run=dry_run)
    except CsvError as e:
        raise HttpError(400, str(e)) from None
    return _report(report)


@router.get(
    "/{event_id}/entries.csv",
    response={403: Error, 404: Error, 400: Error},
    openapi_extra={"responses": _CSV},
    summary="Download the entry list as CSV",
)
def entries_csv(
    request: HttpRequest, event_id: UUID, race_id: UUID | None = None, legacy: bool = False
) -> HttpResponse:
    event = _event(request, event_id, Role.ORGANISER)
    content = export_entries(event, race=_race(event, race_id), legacy=legacy)
    return _download(content, f"{event.slug}-entries.csv", "text/csv; charset=utf-8")


@router.post(
    "/{event_id}/times/import",
    response=IMPORT_RESPONSES,
    summary="Add crossing times from a CSV as manual reads",
    description=(
        "One time column: `at` (ISO date-time), `clock` (time of day), `unix`, or "
        "`elapsed` (since the wave start); the legacy `Result` and `total_time` columns "
        "work too. Times go on `timing_point_id`, or the race's finish line. Rows "
        "already imported are skipped."
    ),
)
def import_times_csv(
    request: HttpRequest,
    event_id: UUID,
    file: File[UploadedFile],
    timing_point_id: Form[UUID | None] = None,
    race_id: Form[UUID | None] = None,
    reason: Form[str] = "",
    dry_run: Form[bool] = False,
) -> Status[ImportReportOut]:
    event = _event(request, event_id, Role.ORGANISER)
    point = None
    if timing_point_id is not None:
        point = TimingPoint.objects.filter(pk=timing_point_id, event=event).first()
        if point is None:
            raise HttpError(400, "That timing point isn't part of this event.")
    try:
        report = import_times(
            event,
            _read(file),
            Actor.of(current_user(request)),
            timing_point=point,
            race=_race(event, race_id),
            filename=file.name or "",
            reason=reason,
            dry_run=dry_run,
        )
    except CsvError as e:
        raise HttpError(400, str(e)) from None
    return _report(report)


@router.get(
    "/{event_id}/results.csv",
    response={403: Error, 404: Error, 400: Error},
    openapi_extra={"responses": _CSV},
    summary="Download results as CSV",
    description="`legacy=true` gives the old system's `race_number,total_time` layout.",
)
def results_csv(
    request: HttpRequest,
    event_id: UUID,
    race_id: UUID | None = None,
    legacy: bool = False,
    decimals: int = 0,
) -> HttpResponse:
    event = _event(request, event_id, Role.VOLUNTEER)
    if not 0 <= decimals <= 3:
        raise HttpError(400, "decimals must be between 0 and 3.")
    content = export_results(event, race=_race(event, race_id), legacy=legacy, decimals=decimals)
    return _download(content, f"{event.slug}-results.csv", "text/csv; charset=utf-8")


@router.get(
    "/{event_id}/bundle",
    response={403: Error, 404: Error},
    openapi_extra={"responses": _ZIP},
    summary="Download the whole event as a bundle (zip)",
)
def event_bundle(request: HttpRequest, event_id: UUID) -> FileResponse:
    return bundle_download(_event(request, event_id, Role.ORGANISER))


@organisations_router.post(
    "/{slug}/events/import",
    response={201: BundleImportOut, 200: BundleImportOut, 400: Error, 403: Error, 404: Error},
    summary="Import an event bundle into this organisation",
    description=(
        "Creates the event (201). If it's already here, `replace` must be set, and the "
        "event is made to match the bundle (200). `event_slug` renames it on the way in."
    ),
)
def import_event_bundle(
    request: HttpRequest,
    slug: str,
    file: File[UploadedFile],
    replace: Form[bool] = False,
    event_slug: Form[str | None] = None,
) -> Status[BundleImportOut]:
    organisation = get_object_or_404(Organisation, slug=slug)
    require_role(request, organisation, Role.OWNER)
    try:
        report = import_bundle(file, organisation, replace=replace, slug=event_slug or None)
    except BundleError as e:
        raise HttpError(400, str(e)) from None
    return Status(
        200 if report.replaced else 201,
        BundleImportOut(
            summary=report.summary(),
            event_id=report.event.pk,
            slug=report.event.slug,
            replaced=report.replaced,
            rows=report.rows,
            crops=report.crops,
            warnings=report.warnings,
        ),
    )
