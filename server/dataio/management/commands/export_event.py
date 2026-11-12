# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from dataio.bundle import bundle_filename, export_bundle
from events.models import Event


def find_event(ref: str) -> Event:
    org_slug, _, event_slug = ref.partition("/")
    if not event_slug:
        raise CommandError("Name the event as <organisation-slug>/<event-slug>.")
    event = (
        Event.objects.select_related("organisation")
        .filter(organisation__slug=org_slug, slug=event_slug)
        .first()
    )
    if event is None:
        raise CommandError(f"No event {ref!r}.")
    return event


class Command(BaseCommand):
    help = "Export an event as a bundle (zip) that import_event can load on any server."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("event", help="<organisation-slug>/<event-slug>")
        parser.add_argument(
            "-o", "--output", help="File to write (default: <slug>-<date>.bundle.zip)"
        )

    def handle(self, *args: Any, event: str, output: str | None = None, **options: Any) -> None:
        found = find_event(event)
        path = Path(output or bundle_filename(found))
        with path.open("wb") as f:
            manifest = export_bundle(found, f)
        rows = sum(meta.get("rows", 0) for meta in manifest["files"].values())
        self.stdout.write(f"Wrote {path} ({rows} rows, {len(manifest['files'])} files).")
