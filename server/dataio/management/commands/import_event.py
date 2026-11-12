# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from typing import Any

from django.core.management.base import BaseCommand, CommandError, CommandParser

from accounts.models import Organisation
from dataio.bundle import BundleError, import_bundle


class Command(BaseCommand):
    help = (
        "Import an event bundle into an organisation. If the event is already here, "
        "--replace makes it match the bundle exactly."
    )

    def add_arguments(self, parser: CommandParser) -> None:
        parser.add_argument("bundle", help="Path to the .bundle.zip file")
        parser.add_argument("organisation", help="Slug of the organisation to import into")
        parser.add_argument("--replace", action="store_true", help="Replace the event if it exists")
        parser.add_argument("--slug", help="Use this event slug instead of the bundle's")

    def handle(
        self,
        *args: Any,
        bundle: str,
        organisation: str,
        replace: bool = False,
        slug: str | None = None,
        **options: Any,
    ) -> None:
        org = Organisation.objects.filter(slug=organisation).first()
        if org is None:
            raise CommandError(f"No organisation {organisation!r}.")
        try:
            report = import_bundle(bundle, org, replace=replace, slug=slug)
        except (BundleError, OSError) as e:
            raise CommandError(str(e)) from None
        for warning in report.warnings:
            self.stderr.write(f"Warning: {warning}")
        self.stdout.write(report.summary())
