# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Django admin: the stopgap organiser UI until the web console exists (Phase 4)."""

from django.contrib import admin

from events.models import (
    CategoryRule,
    CategoryScheme,
    Entry,
    Event,
    Race,
    Split,
    TimingPoint,
    Wave,
)


class CategoryRuleInline(admin.TabularInline[CategoryRule, CategoryScheme]):
    model = CategoryRule
    extra = 0


@admin.register(CategoryScheme)
class CategorySchemeAdmin(admin.ModelAdmin[CategoryScheme]):
    list_display = ("name", "organisation", "age_basis")
    list_filter = ("organisation",)
    inlines = (CategoryRuleInline,)


class RaceInline(admin.TabularInline[Race, Event]):
    model = Race
    extra = 0
    fields = ("name", "distance_m", "ranking_basis", "category_scheme", "order")
    show_change_link = True


class TimingPointInline(admin.TabularInline[TimingPoint, Event]):
    model = TimingPoint
    extra = 0


@admin.register(Event)
class EventAdmin(admin.ModelAdmin[Event]):
    list_display = ("name", "organisation", "start_date", "status")
    list_filter = ("status", "organisation")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
    inlines = (TimingPointInline, RaceInline)


class WaveInline(admin.TabularInline[Wave, Race]):
    model = Wave
    extra = 0


class SplitInline(admin.TabularInline[Split, Race]):
    model = Split
    extra = 0
    fields = ("order", "kind", "name", "timing_point", "distance_m", "min_elapsed")


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin[Race]):
    list_display = ("name", "event", "distance_m", "ranking_basis")
    list_filter = ("event",)
    inlines = (WaveInline, SplitInline)


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin[Entry]):
    list_display = ("bib", "given_name", "family_name", "race", "gender", "club", "status")
    list_filter = ("event", "race", "status", "gender")
    search_fields = ("bib", "given_name", "family_name", "club", "email")
    list_select_related = ("race",)
