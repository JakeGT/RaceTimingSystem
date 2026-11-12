# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Read-only views of stored results. They're rebuilt automatically; to change one,
change the reads or the entry."""

from django.contrib import admin

from results.models import RaceResults, Result
from timing.admin import ReadOnlyAdmin


@admin.register(Result)
class ResultAdmin(ReadOnlyAdmin[Result]):
    list_display = (
        "overall_position",
        "entry",
        "race",
        "outcome",
        "gun_time",
        "net_time",
        "category",
        "category_position",
        "flags",
    )
    list_filter = ("event", "race", "outcome")
    search_fields = ("entry__bib", "entry__given_name", "entry__family_name")
    list_select_related = ("entry", "race")


@admin.register(RaceResults)
class RaceResultsAdmin(ReadOnlyAdmin[RaceResults]):
    list_display = ("race", "computed_at", "warnings")
    list_filter = ("event",)
