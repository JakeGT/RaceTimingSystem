# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Django admin: the stopgap organiser UI until the web console exists (Phase 4)."""

from typing import Any, cast

from django import forms
from django.contrib import admin, messages
from django.db.models import QuerySet
from django.http import HttpRequest

from accounts.models import User
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
from timing import review


def actor(request: HttpRequest) -> review.Actor:
    return review.Actor.of(cast(User, request.user))


class ChangeReasonForm[M: Any](forms.ModelForm[M]):
    """Adds a "reason" box for changes that end up in the audit log."""

    change_reason = forms.CharField(
        required=False, max_length=255, help_text="Recorded in the audit log."
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
    readonly_fields = ("start_at",)  # starts are audited: use the Waves page


class WaveForm(ChangeReasonForm[Wave]):
    class Meta:
        model = Wave
        fields = ("race", "name", "order", "start_at")

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        changing_start = (
            self.instance.pk and self.instance.start_at and "start_at" in self.changed_data
        )
        if changing_start and not data.get("change_reason", "").strip():
            self.add_error("change_reason", "Say why the start time is changing.")
        return data


@admin.register(Wave)
class WaveAdmin(admin.ModelAdmin[Wave]):
    form = WaveForm
    list_display = ("name", "race", "start_at")
    list_filter = ("event", "race")
    actions = ("start_now",)

    @admin.action(description="Start selected waves now")
    def start_now(self, request: HttpRequest, queryset: QuerySet[Wave]) -> None:
        started = 0
        for wave in queryset.filter(start_at__isnull=True):
            review.start_wave(wave, actor(request))
            started += 1
        skipped = queryset.count() - started
        messages.success(request, f"Started {started} wave(s).")
        if skipped:
            messages.warning(
                request,
                f"{skipped} wave(s) had already started: edit them to correct a start time.",
            )

    def save_model(self, request: HttpRequest, obj: Wave, form: Any, change: bool) -> None:
        if "start_at" not in form.changed_data or obj.start_at is None:
            super().save_model(request, obj, form, change)
            return
        new_start = obj.start_at
        obj.start_at = form.initial.get("start_at")
        super().save_model(request, obj, form, change)
        review.start_wave(
            obj, actor(request), at=new_start, reason=form.cleaned_data["change_reason"]
        )
        obj.refresh_from_db()


class SplitInline(admin.TabularInline[Split, Race]):
    model = Split
    extra = 0
    fields = ("order", "kind", "name", "timing_point", "distance_m", "min_elapsed")


@admin.register(Race)
class RaceAdmin(admin.ModelAdmin[Race]):
    list_display = ("name", "event", "distance_m", "ranking_basis")
    list_filter = ("event",)
    inlines = (WaveInline, SplitInline)


class EntryForm(ChangeReasonForm[Entry]):
    class Meta:
        model = Entry
        exclude = ("status_reason",)  # noqa: DJ006

    def clean(self) -> dict[str, Any]:
        data = super().clean() or {}
        dsq = data.get("status") == Entry.Status.DSQ and "status" in self.changed_data
        if dsq and not data.get("change_reason", "").strip():
            self.add_error("change_reason", "Say why: disqualifications are published.")
        return data


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin[Entry]):
    form = EntryForm
    readonly_fields = ("status_reason",)

    def save_model(self, request: HttpRequest, obj: Entry, form: Any, change: bool) -> None:
        if not change or "status" not in form.changed_data:
            super().save_model(request, obj, form, change)
            return
        new_status = Entry.Status(obj.status)
        obj.status = form.initial["status"]
        super().save_model(request, obj, form, change)
        review.set_entry_status(obj, new_status, actor(request), form.cleaned_data["change_reason"])
        obj.refresh_from_db()

    list_display = ("bib", "given_name", "family_name", "race", "gender", "club", "status")
    list_filter = ("event", "race", "status", "gender")
    search_fields = ("bib", "given_name", "family_name", "club", "email")
    list_select_related = ("race",)
