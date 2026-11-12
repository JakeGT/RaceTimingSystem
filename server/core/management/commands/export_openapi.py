# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Write the API's OpenAPI document to protocol/openapi.json.

The committed file is the device protocol contract that the mobile app and the web
client are generated from. CI runs this with --check so it can't drift from the code.
"""

import json
from argparse import ArgumentParser
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from config.api import api

DEFAULT_PATH = Path(settings.BASE_DIR).parent / "protocol" / "openapi.json"


def render() -> str:
    schema = api.get_openapi_schema(path_prefix="/api/v1")
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


class Command(BaseCommand):
    help = "Export the OpenAPI document to protocol/openapi.json."

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument("--path", type=Path, default=DEFAULT_PATH)
        parser.add_argument("--check", action="store_true", help="Fail if the file is out of date.")

    def handle(self, *args: Any, path: Path, check: bool, **options: Any) -> None:
        content = render()
        if check:
            current = path.read_text() if path.exists() else ""
            if current != content:
                raise CommandError(
                    f"{path} is out of date. Run `uv run python manage.py export_openapi`."
                )
            self.stdout.write(f"{path} is up to date.")
            return
        path.write_text(content)
        self.stdout.write(f"Wrote {path}.")
