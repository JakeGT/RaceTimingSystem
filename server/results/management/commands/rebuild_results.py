# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from events.models import Event
from results.services import rebuild_event
from timing.fusion import fuse_pending


class Command(BaseCommand):
    help = "Fuse any unfused observations, then rebuild every race's results."

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("event", nargs="?", help="Event slug (default: all events).")

    def handle(self, *args: Any, event: str | None = None, **options: Any) -> None:
        events = Event.objects.all()
        if event:
            events = events.filter(slug=event)
            if not events.exists():
                raise CommandError(f"No event with slug {event!r}.")
        for ev in events:
            fuse_pending(ev)
            rebuild_event(ev)
            self.stdout.write(f"Rebuilt {ev}")
