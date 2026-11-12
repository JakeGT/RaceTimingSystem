# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Event bundles: a full round trip, idempotent re-import, and hostile bundles."""

import hashlib
import io
import json
import uuid
import zipfile
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from django.core import serializers
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage

from accounts.models import Organisation, User
from dataio import bundle
from dataio.bundle import BundleError, export_bundle, import_bundle
from dataio.entries import import_entries
from dataio.tests.conftest import GUN, LEGACY_PARTICIPANTS
from events.models import CategoryScheme, Entry, Event, Race, Split, TimingPoint, Wave
from results.models import Result
from timing import review
from timing.fusion import fuse_pending
from timing.models import Adjustment, Device, Heartbeat, Observation, PairingCode, Read

pytestmark = pytest.mark.django_db

CROP = b"\xff\xd8\xff\xe0 not really a jpeg"


@pytest.fixture
def full_event(
    event: Event, race: Race, finish: Split, started: Wave, referee: review.Actor
) -> Event:
    """An event after race day: entries, phones, observations with crops, reviewed
    reads, a manual read, heartbeats and results."""
    assert import_entries(event, LEGACY_PARTICIPANTS).ok
    pairing, _ = PairingCode.issue(event, finish.timing_point)
    phone, _ = Device.pair(pairing, name="Left", platform="android")
    Heartbeat.objects.create(device=phone, battery_pct=81, fps=29.5)
    for n, (bib, confidence) in enumerate([("1", 0.97), ("2", 0.4), ("3", 0.9)]):
        at = GUN + timedelta(minutes=25 + n, microseconds=123456)
        obs = Observation.objects.create(
            id=uuid.uuid7(),
            event=event,
            device=phone,
            timing_point=finish.timing_point,
            captured_at_device=at,
            clock_offset_ms=12,
            captured_at=at,
            candidates=[{"bib": bib, "confidence": confidence}],
        )
        obs.crop.save("crop.jpg", ContentFile(CROP + bib.encode()), save=True)
    fuse_pending(event)
    review.confirm_read(Read.objects.get(bib="2"), referee)
    review.add_manual_read(
        event, finish.timing_point, "4", GUN + timedelta(minutes=31), referee, "Stopwatch"
    )
    return event


def snapshot(event: Event) -> dict[str, list[dict[str, Any]]]:
    """Everything a bundle carries, as plain data."""
    return {
        bundle.label(model): serializers.serialize("python", qs, fields=bundle._fields(model))
        for model, qs in bundle._querysets(event)
    }


def export(event: Event) -> bytes:
    out = io.BytesIO()
    export_bundle(event, out)
    return out.getvalue()


def wipe(event: Event) -> None:
    """As if the event had never been on this server."""
    pk = event.pk
    bundle._clear(event)
    event.delete()
    event.pk = pk  # delete() blanks it; tests still need to know which event it was


def files(data: bytes) -> dict[str, bytes]:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        return {name: zf.read(name) for name in zf.namelist()}


def rebuild(data: bytes, change: Callable[[dict[str, bytes], dict[str, Any]], None]) -> bytes:
    """A modified copy of a bundle, with the manifest's checksums fixed up to match,
    so the import's own checks (not the checksum) have to catch the change."""
    contents = files(data)
    manifest = json.loads(contents.pop("manifest.json"))
    change(contents, manifest)
    for path, content in contents.items():
        manifest["files"].setdefault(path, {})["sha256"] = hashlib.sha256(content).hexdigest()
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w") as zf:
        for path, content in contents.items():
            zf.writestr(path, content)
        zf.writestr("manifest.json", json.dumps(manifest))
    return out.getvalue()


def edit_rows(path: str, edit: Callable[[dict[str, Any]], None]) -> Callable[..., None]:
    def change(contents: dict[str, bytes], manifest: dict[str, Any]) -> None:
        rows = [json.loads(line) for line in contents[path].decode().splitlines()]
        for row in rows:
            edit(row)
        contents[path] = "".join(json.dumps(r) + "\n" for r in rows).encode()

    return change


class TestRoundTrip:
    def test_to_a_server_that_never_had_the_event(
        self, full_event: Event, organisation: Organisation
    ) -> None:
        before = snapshot(full_event)
        old_tokens = set(Device.objects.values_list("token_hash", flat=True))
        crops = {str(o.crop.name): o.crop.read() for o in Observation.objects.all()}
        data = export(full_event)
        wipe(full_event)
        for name in crops:
            default_storage.delete(name)

        report = import_bundle(io.BytesIO(data), organisation)

        assert (report.replaced, report.crops, report.warnings) == (False, 3, [])
        assert report.rows["events.entry"] == 6 and report.rows["timing.adjustment"] == 2
        event = Event.objects.get(pk=full_event.pk)
        assert snapshot(event) == before  # including created_at and microsecond times
        for name, content in crops.items():
            assert default_storage.open(name).read() == content
        # Phones have to pair again: their old tokens don't travel.
        assert not old_tokens & set(Device.objects.values_list("token_hash", flat=True))
        # Results are rebuilt rather than copied.
        assert Result.objects.filter(event=event, outcome=Result.Outcome.FINISHED).count() == 4
        assert Adjustment.objects.filter(actor__email="ref@example.com").count() == 2

    def test_reimport_is_idempotent(self, full_event: Event, organisation: Organisation) -> None:
        first = export(full_event)
        import_bundle(io.BytesIO(first), organisation, replace=True)
        import_bundle(io.BytesIO(first), organisation, replace=True)
        second = export(Event.objects.get(pk=full_event.pk))
        a, b = files(first), files(second)
        a.pop("manifest.json"), b.pop("manifest.json")
        assert a == b

    def test_replace_drops_changes_made_since(
        self, full_event: Event, organisation: Organisation, race: Race
    ) -> None:
        data = export(full_event)
        Entry.objects.filter(bib="1").update(given_name="Changed")
        Entry.objects.create(race=race, bib="999", given_name="Late entry")
        Entry.objects.filter(bib="6").delete()
        with pytest.raises(BundleError, match="already on this server"):
            import_bundle(io.BytesIO(data), organisation)
        assert import_bundle(io.BytesIO(data), organisation, replace=True).replaced
        bibs = set(Entry.objects.filter(event=full_event).values_list("bib", flat=True))
        assert bibs == {"1", "2", "3", "4", "5", "6"}
        assert Entry.objects.get(bib="1").given_name == "John"

    def test_staff_who_are_not_here_stay_as_names(
        self, full_event: Event, organisation: Organisation
    ) -> None:
        data = export(full_event)
        wipe(full_event)
        User.objects.filter(email="ref@example.com").delete()
        import_bundle(io.BytesIO(data), organisation)
        log = Adjustment.objects.filter(event=full_event)
        assert {(a.actor_id, a.actor_label) for a in log} == {(None, "ref@example.com")}


class TestWhereItLands:
    @pytest.fixture
    def other_org(self, db: None) -> Organisation:
        return Organisation.objects.create(name="Tavistock AC", slug="tavistock")

    def test_event_belongs_to_another_organisation_here(
        self, full_event: Event, other_org: Organisation
    ) -> None:
        with pytest.raises(BundleError, match="in Exeter Harriers"):
            import_bundle(io.BytesIO(export(full_event)), other_org, replace=True)

    def test_category_scheme_copied_into_another_organisation(
        self, full_event: Event, other_org: Organisation, scheme: CategoryScheme
    ) -> None:
        data = export(full_event)
        wipe(full_event)
        import_bundle(io.BytesIO(data), other_org)
        copied = Race.objects.get(event_id=full_event.pk).category_scheme
        assert copied is not None and copied.pk != scheme.pk
        assert (copied.organisation, copied.name) == (other_org, "Road running")
        assert [r.code for r in copied.rules.all()] == [r.code for r in scheme.rules.all()]
        assert scheme.rules.count() == 5  # the original is untouched

    def test_existing_scheme_is_never_changed(
        self, full_event: Event, organisation: Organisation, scheme: CategoryScheme
    ) -> None:
        data = export(full_event)
        scheme.rules.filter(code="OPEN").delete()
        import_bundle(io.BytesIO(data), organisation, replace=True)
        assert scheme.rules.count() == 4

    def test_scheme_name_clash_gets_a_suffix(
        self, full_event: Event, organisation: Organisation, scheme: CategoryScheme
    ) -> None:
        data = export(full_event)
        wipe(full_event)
        scheme.delete()
        CategoryScheme.objects.create(organisation=organisation, name="Road running")
        report = import_bundle(io.BytesIO(data), organisation)
        assert "added as 'Road running (Riverside 10K)'" in report.warnings[0]

    def test_slug_clash_and_rename(self, full_event: Event, organisation: Organisation) -> None:
        data = export(full_event)
        wipe(full_event)
        Event.objects.create(
            organisation=organisation, name="Other", slug="riverside-10k", start_date=GUN.date()
        )
        with pytest.raises(BundleError, match="already has an event at /riverside-10k"):
            import_bundle(io.BytesIO(data), organisation)
        report = import_bundle(io.BytesIO(data), organisation, slug="riverside-10k-2026")
        assert report.event.slug == "riverside-10k-2026"


class TestHostileBundles:
    @pytest.fixture
    def data(self, full_event: Event) -> bytes:
        return export(full_event)

    def check(self, data: bytes, organisation: Organisation, match: str) -> None:
        before = Entry.objects.count(), Read.objects.count()
        with pytest.raises(BundleError, match=match):
            import_bundle(io.BytesIO(data), organisation, replace=True)
        assert (Entry.objects.count(), Read.objects.count()) == before

    def test_not_a_zip(self, organisation: Organisation) -> None:
        self.check(b"hello", organisation, "isn't a zip")

    def test_damaged_file(self, data: bytes, organisation: Organisation) -> None:
        contents = files(data)
        contents["data/events.entry.jsonl"] = contents["data/events.entry.jsonl"].replace(
            b"John", b"Jonn"
        )
        out = io.BytesIO()
        with zipfile.ZipFile(out, "w") as zf:
            for path, content in contents.items():
                zf.writestr(path, content)
        self.check(out.getvalue(), organisation, "doesn't match its checksum")

    def test_newer_schema(self, data: bytes, organisation: Organisation) -> None:
        def newer(contents: dict[str, bytes], manifest: dict[str, Any]) -> None:
            manifest["schema_version"] = bundle.SCHEMA_VERSION + 1

        self.check(rebuild(data, newer), organisation, "newer version of the server")

    def test_extra_file(self, data: bytes, organisation: Organisation) -> None:
        def extra(contents: dict[str, bytes], manifest: dict[str, Any]) -> None:
            contents["media/crops/../../settings.py"] = b"x"

        self.check(rebuild(data, extra), organisation, "unexpected file")

    def test_row_of_another_model(self, data: bytes, organisation: Organisation) -> None:
        def smuggle(row: dict[str, Any]) -> None:
            row["model"] = "accounts.user"

        changed = rebuild(data, edit_rows("data/events.entry.jsonl", smuggle))
        self.check(changed, organisation, "isn't a events.entry row")

    def test_link_to_another_events_data(
        self, data: bytes, organisation: Organisation, full_event: Event
    ) -> None:
        other = Event.objects.create(
            organisation=organisation, name="Other", slug="other", start_date=GUN.date()
        )
        point = TimingPoint.objects.create(event=other, name="Finish")

        def repoint(row: dict[str, Any]) -> None:
            row["fields"]["timing_point"] = str(point.pk)

        changed = rebuild(data, edit_rows("data/timing.read.jsonl", repoint))
        self.check(changed, organisation, "points at a events.timingpoint that isn't in it")

    def test_overwriting_another_events_row(
        self, data: bytes, organisation: Organisation, race: Race
    ) -> None:
        other = Event.objects.create(
            organisation=organisation, name="Other", slug="other", start_date=GUN.date()
        )
        victim = Entry.objects.create(
            race=Race.objects.create(event=other, name="5K", distance_m=5000),
            bib="1",
            given_name="Victim",
        )

        def steal(row: dict[str, Any]) -> None:
            if row["fields"]["bib"] == "1":
                row["pk"] = str(victim.pk)

        changed = rebuild(data, edit_rows("data/events.entry.jsonl", steal))
        self.check(changed, organisation, "belongs to another event here")
        assert Entry.objects.get(pk=victim.pk).given_name == "Victim"

    def test_invalid_values(self, data: bytes, organisation: Organisation) -> None:
        def bad_bib(row: dict[str, Any]) -> None:
            row["fields"]["bib"] = "1 OR 1=1"

        changed = rebuild(data, edit_rows("data/events.entry.jsonl", bad_bib))
        self.check(changed, organisation, "is invalid: bib")

    def test_unknown_field(self, data: bytes, organisation: Organisation) -> None:
        def extra_field(row: dict[str, Any]) -> None:
            row["fields"]["is_superuser"] = True

        changed = rebuild(data, edit_rows("data/events.entry.jsonl", extra_field))
        self.check(changed, organisation, "has a bad row")
