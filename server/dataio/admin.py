# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin pages for data in and out, until the organiser console exists (Phase 4).

Adds a "Data in/out" page to each event (CSV imports and downloads) and an
"Import bundle" page to the event list.
"""

from typing import Any
from uuid import UUID

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.template.response import TemplateResponse
from django.urls import URLPattern, path, reverse

from accounts.models import Organisation
from dataio.api import bundle_download
from dataio.bundle import BundleError, import_bundle
from dataio.csvfiles import CsvError, ImportReport
from dataio.entries import export_entries, import_entries
from dataio.results_csv import export_results
from dataio.times import import_times
from events.admin import EventAdmin, actor
from events.models import Event, Race, TimingPoint

MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class EntriesImportForm(forms.Form):
    file = forms.FileField(help_text="This system's entries CSV, or a legacy participants CSV.")
    race = forms.ModelChoiceField(
        Race.objects.none(),
        required=False,
        help_text="For rows without a race column. Not needed if the event has one race.",
    )
    dry_run = forms.BooleanField(required=False, help_text="Check the file without saving.")

    def __init__(self, event: Event, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["race"].queryset = event.races.all()  # type: ignore[attr-defined]


class TimesImportForm(forms.Form):
    file = forms.FileField(
        help_text="Columns: bib plus one of at, clock, unix or elapsed "
        "(legacy Result or total_time files work too)."
    )
    timing_point = forms.ModelChoiceField(
        TimingPoint.objects.none(), required=False, help_text="Default: the finish line."
    )
    race = forms.ModelChoiceField(
        Race.objects.none(), required=False, help_text="Narrows down which finish line."
    )
    reason = forms.CharField(required=False, max_length=200, help_text="Added to the audit log.")
    dry_run = forms.BooleanField(required=False, help_text="Check the file without saving.")

    def __init__(self, event: Event, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.fields["timing_point"].queryset = event.timing_points.all()  # type: ignore[attr-defined]
        self.fields["race"].queryset = event.races.all()  # type: ignore[attr-defined]


class BundleImportForm(forms.Form):
    file = forms.FileField(help_text="A .bundle.zip exported from this or another server.")
    organisation = forms.ModelChoiceField(Organisation.objects.all())
    replace = forms.BooleanField(
        required=False,
        help_text="If the event is already here, make it match the bundle exactly. "
        "Anything added here since the bundle was made is lost.",
    )
    slug = forms.SlugField(required=False, help_text="Optional: a different slug for the event.")


def _too_big(upload: Any) -> bool:
    return bool(upload.size and upload.size > MAX_UPLOAD_BYTES)


class EventDataAdmin(EventAdmin):
    change_form_template = "admin/dataio/event_change_form.html"
    change_list_template = "admin/dataio/event_change_list.html"

    def get_urls(self) -> list[URLPattern]:
        wrap = self.admin_site.admin_view
        return [
            path("<uuid:event_id>/data/", wrap(self.data_view), name="events_event_data"),
            path(
                "<uuid:event_id>/data/<str:what>/",
                wrap(self.download_view),
                name="events_event_download",
            ),
            path("import-bundle/", wrap(self.bundle_import_view), name="events_event_import"),
            *super().get_urls(),
        ]

    def _event(self, request: HttpRequest, event_id: UUID) -> Event:
        event = get_object_or_404(Event.objects.select_related("organisation"), pk=event_id)
        if not self.has_change_permission(request, event):
            raise PermissionDenied
        return event

    def data_view(self, request: HttpRequest, event_id: UUID) -> HttpResponse:
        event = self._event(request, event_id)
        which = request.POST.get("form")
        entries_form = EntriesImportForm(
            event, *((request.POST, request.FILES) if which == "entries" else ())
        )
        times_form = TimesImportForm(
            event, *((request.POST, request.FILES) if which == "times" else ())
        )
        report: ImportReport | None = None
        if which == "entries" and entries_form.is_valid():
            report = self._run(
                request,
                entries_form,
                lambda data: import_entries(
                    event,
                    data,
                    race=entries_form.cleaned_data["race"],
                    dry_run=entries_form.cleaned_data["dry_run"],
                ),
            )
        elif which == "times" and times_form.is_valid():
            data = times_form.cleaned_data
            report = self._run(
                request,
                times_form,
                lambda raw: import_times(
                    event,
                    raw,
                    actor(request),
                    timing_point=data["timing_point"],
                    race=data["race"],
                    filename=data["file"].name,
                    reason=data["reason"],
                    dry_run=data["dry_run"],
                ),
            )
        if report is not None and report.ok and not report.dry_run:
            return HttpResponseRedirect(request.path)
        context = {
            **self.admin_site.each_context(request),
            "title": f"Data in/out: {event}",
            "opts": self.opts,
            "original": event,
            "event": event,
            "entries_form": entries_form,
            "times_form": times_form,
            "report": report,
            "downloads": [
                ("entries", "Entry list (CSV)"),
                ("entries-legacy", "Entry list, legacy layout (CSV)"),
                ("results", "Results (CSV)"),
                ("results-legacy", "Results, legacy race_number,total_time (CSV)"),
                ("bundle", "Whole event bundle (zip)"),
            ],
        }
        return TemplateResponse(request, "admin/dataio/event_data.html", context)

    def _run(self, request: HttpRequest, form: forms.Form, run: Any) -> ImportReport | None:
        upload = form.cleaned_data["file"]
        if _too_big(upload):
            form.add_error("file", "That file is too big for a CSV (the limit is 10 MB).")
            return None
        try:
            report: ImportReport = run(upload.read())
        except CsvError as e:
            form.add_error("file", str(e))
            return None
        level = messages.SUCCESS if report.ok else messages.ERROR
        messages.add_message(request, level, report.summary())
        for warning in report.warnings:
            messages.warning(request, warning)
        if report.ignored_columns:
            messages.info(request, f"Ignored columns: {', '.join(report.ignored_columns)}")
        return report

    def download_view(
        self, request: HttpRequest, event_id: UUID, what: str
    ) -> HttpResponse | FileResponse:
        event = self._event(request, event_id)
        if what == "bundle":
            return bundle_download(event)
        kind, _, variant = what.partition("-")
        legacy = variant == "legacy"
        if kind == "entries":
            content = export_entries(event, legacy=legacy)
        elif kind == "results":
            content = export_results(event, legacy=legacy)
        else:
            raise Http404
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{event.slug}-{what}.csv"'
        return response

    def bundle_import_view(self, request: HttpRequest) -> HttpResponse:
        if not self.has_add_permission(request):
            raise PermissionDenied
        form = BundleImportForm(request.POST or None, request.FILES or None)
        if request.method == "POST" and form.is_valid():
            data = form.cleaned_data
            try:
                report = import_bundle(
                    data["file"],
                    data["organisation"],
                    replace=data["replace"],
                    slug=data["slug"] or None,
                )
            except BundleError as e:
                form.add_error(None, str(e))
            else:
                messages.success(request, report.summary())
                for warning in report.warnings:
                    messages.warning(request, warning)
                return HttpResponseRedirect(
                    reverse("admin:events_event_change", args=[report.event.pk])
                )
        context = {
            **self.admin_site.each_context(request),
            "title": "Import an event bundle",
            "opts": self.opts,
            "form": form,
        }
        return TemplateResponse(request, "admin/dataio/bundle_import.html", context)


admin.site.unregister(Event)
admin.site.register(Event, EventDataAdmin)
