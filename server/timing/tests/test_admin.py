# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Admin changes to timing data go through timing.review and land in the audit log."""

from datetime import timedelta

import pytest
from django.test import Client

from accounts.models import User
from events.models import Entry, Event, TimingPoint, Wave
from results.models import Result
from timing.fusion import fuse_pending
from timing.models import Adjustment, Read
from timing.tests.conftest import GUN, MakeObservation

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("finish", "started")]
Action = Adjustment.Action


@pytest.fixture
def staff(client: Client) -> Client:
    client.force_login(User.objects.create_superuser(email="root@example.com", password="x"))
    return client


@pytest.fixture
def unreadable(event: Event, entries: dict[str, Entry], observe: MakeObservation) -> Read:
    observe({}, 2400)
    fuse_pending(event)
    return Read.objects.get()


def change(read: Read, **fields: str) -> dict[str, str]:
    data = {
        "bib": read.bib,
        "at_0": f"{read.at:%Y-%m-%d}",
        "at_1": f"{read.at:%H:%M:%S.%f}",
        "change_reason": "",
        "observations-TOTAL_FORMS": "0",
        "observations-INITIAL_FORMS": "0",
    }
    data.update(fields)
    return data


def test_assign_bib_in_admin(staff: Client, unreadable: Read, entries: dict[str, Entry]) -> None:
    url = f"/admin/timing/read/{unreadable.pk}/change/"
    assert staff.get(url).status_code == 200
    response = staff.post(url, change(unreadable, bib="102"))
    assert response.status_code == 302, response.content.decode()[:2000]
    log = Adjustment.objects.get()
    assert (log.action, log.actor_label) == (Action.READ_BIB_CHANGED, "root@example.com")
    assert Result.objects.get(entry=entries["102"]).outcome == "finished"


def test_admin_refuses_unentered_bib(staff: Client, unreadable: Read) -> None:
    response = staff.post(
        f"/admin/timing/read/{unreadable.pk}/change/", change(unreadable, bib="999")
    )
    assert response.status_code == 200
    assert b"Nobody in this event has bib" in response.content
    assert not Adjustment.objects.exists()


def test_time_change_needs_reason(
    staff: Client, unreadable: Read, entries: dict[str, Entry]
) -> None:
    new = unreadable.at + timedelta(seconds=3)
    data = change(unreadable, bib="101", at_1=f"{new:%H:%M:%S.%f}")
    response = staff.post(f"/admin/timing/read/{unreadable.pk}/change/", data)
    assert b"Say why" in response.content
    data["change_reason"] = "photo"
    assert staff.post(f"/admin/timing/read/{unreadable.pk}/change/", data).status_code == 302
    assert set(Adjustment.objects.values_list("action", flat=True)) == {
        Action.READ_BIB_CHANGED,
        Action.READ_TIME_CHANGED,
    }


def test_add_manual_read_in_admin(
    staff: Client, event: Event, finish_line: TimingPoint, entries: dict[str, Entry]
) -> None:
    at = GUN + timedelta(minutes=41)
    response = staff.post(
        "/admin/timing/read/add/",
        {
            "event": str(event.pk),
            "timing_point": str(finish_line.pk),
            "bib": "103",
            "at_0": f"{at:%Y-%m-%d}",
            "at_1": f"{at:%H:%M:%S}",
            "change_reason": "stopwatch",
            "observations-TOTAL_FORMS": "0",
            "observations-INITIAL_FORMS": "0",
        },
    )
    assert response.status_code == 302, response.content.decode()[:2000]
    assert Read.objects.get().state == Read.State.MANUAL
    assert Adjustment.objects.get().action == Action.READ_ADDED


def test_reject_action(
    staff: Client, event: Event, entries: dict[str, Entry], observe: MakeObservation
) -> None:
    observe({"101": 0.95}, 2400)
    fuse_pending(event)
    read = Read.objects.get()
    staff.post(
        "/admin/timing/read/",
        {"action": "reject", "_selected_action": [str(read.pk)]},
    )
    read.refresh_from_db()
    assert read.state == Read.State.REJECTED
    assert Adjustment.objects.get().action == Action.READ_REJECTED


def test_start_wave_action(staff: Client, race: object, entries: dict[str, Entry]) -> None:
    fun = Wave.objects.create(race=race, name="Fun run")  # type: ignore[misc]
    staff.post("/admin/events/wave/", {"action": "start_now", "_selected_action": [str(fun.pk)]})
    fun.refresh_from_db()
    assert fun.start_at is not None
    assert Adjustment.objects.get().wave == fun


def test_dsq_in_admin_is_audited(staff: Client, entries: dict[str, Entry]) -> None:
    entry = entries["101"]
    url = f"/admin/events/entry/{entry.pk}/change/"
    data = {
        "race": str(entry.race_id),
        "wave": str(entry.wave_id),
        "bib": "101",
        "given_name": "Ada",
        "gender": entry.gender,
        "declared_age": "30",
        "status": "dsq",
        "change_reason": "",
    }
    assert b"disqualifications are published" in staff.post(url, data).content
    data["change_reason"] = "cut the course"
    assert staff.post(url, data).status_code == 302
    entry.refresh_from_db()
    assert (entry.status, entry.status_reason) == ("dsq", "cut the course")
    assert Adjustment.objects.get().action == Action.ENTRY_STATUS_CHANGED
