# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Staff sign-in, roles, 2FA enforcement and invitations (ADR 0002)."""

import json
import re
from collections.abc import Callable
from datetime import timedelta
from typing import Any

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import (
    TOTP,
    format_hotp_value,
    generate_totp_secret,
    hotp_value,
    yield_hotp_counters_from_time,
)
from django.core import mail
from django.test import Client
from django.utils import timezone

from accounts.models import Invitation, Membership, Organisation, Role, User
from events.models import Event, TimingPoint
from timing.models import PairingCode

API = "/api/v1"
AUTH = "/api/auth"
PASSWORD = "correct horse battery staple"

pytestmark = pytest.mark.django_db


def call(client: Client, method: str, path: str, body: object = None, **headers: str) -> Any:
    return getattr(client, method)(
        path,
        json.dumps(body) if body is not None else None,
        content_type="application/json",
        headers=headers or None,
    )


def with_2fa(user: User) -> User:
    Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={"secret": "x"})
    return user


@pytest.fixture
def make_member(organisation: Organisation) -> Callable[..., User]:
    def make(email: str, role: Role, *, mfa: bool = True) -> User:
        user = User.objects.create_user(email=email, password=PASSWORD)
        EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
        Membership.objects.create(user=user, organisation=organisation, role=role)
        return with_2fa(user) if mfa else user

    return make


@pytest.fixture
def owner(make_member: Callable[..., User]) -> User:
    return make_member("owner@example.com", Role.OWNER)


@pytest.fixture
def volunteer(make_member: Callable[..., User]) -> User:
    return make_member("vol@example.com", Role.VOLUNTEER, mfa=False)


def signed_in(user: User) -> Client:
    client = Client()
    client.force_login(user)
    return client


class TestMe:
    def test_requires_sign_in(self, client: Client) -> None:
        assert call(client, "get", f"{API}/staff/me").status_code == 401

    def test_lists_roles(self, owner: User, organisation: Organisation) -> None:
        body = call(signed_in(owner), "get", f"{API}/staff/me").json()
        assert body["organisations"] == [
            {"slug": organisation.slug, "name": organisation.name, "role": "owner"}
        ]
        assert (body["mfa_enabled"], body["mfa_required"]) == (True, False)

    def test_flags_missing_2fa(self, make_member: Callable[..., User]) -> None:
        organiser = make_member("org@example.com", Role.ORGANISER, mfa=False)
        body = call(signed_in(organiser), "get", f"{API}/staff/me").json()
        assert body["mfa_required"] is True

    def test_volunteers_do_not_need_2fa(self, volunteer: User) -> None:
        assert call(signed_in(volunteer), "get", f"{API}/staff/me").json()["mfa_required"] is False


class TestRoles:
    def url(self, organisation: Organisation, rest: str = "members") -> str:
        return f"{API}/staff/organisations/{organisation.slug}/{rest}"

    def test_members_visible_to_volunteers(
        self, owner: User, volunteer: User, organisation: Organisation
    ) -> None:
        response = call(signed_in(volunteer), "get", self.url(organisation))
        assert response.status_code == 200
        assert {m["email"] for m in response.json()} == {owner.email, volunteer.email}

    def test_outsiders_get_404(self, organisation: Organisation) -> None:
        outsider = with_2fa(User.objects.create_user(email="x@example.com", password=PASSWORD))
        assert call(signed_in(outsider), "get", self.url(organisation)).status_code == 404

    def test_organiser_without_2fa_is_locked_out(
        self, make_member: Callable[..., User], organisation: Organisation
    ) -> None:
        organiser = make_member("org@example.com", Role.ORGANISER, mfa=False)
        response = call(signed_in(organiser), "get", self.url(organisation))
        assert response.status_code == 403
        assert response.json()["code"] == "mfa_required"

    def test_superuser_is_owner_everywhere(self, organisation: Organisation) -> None:
        root = with_2fa(User.objects.create_superuser(email="root@example.com", password="x"))
        assert call(signed_in(root), "get", self.url(organisation)).status_code == 200

    def test_owner_changes_role(
        self, owner: User, volunteer: User, organisation: Organisation
    ) -> None:
        m = Membership.objects.get(user=volunteer)
        response = call(
            signed_in(owner),
            "patch",
            self.url(organisation, f"members/{m.pk}"),
            {"role": "organiser"},
        )
        assert response.status_code == 200
        assert response.json()["role"] == "organiser"

    def test_volunteer_cannot_change_roles(
        self, owner: User, volunteer: User, organisation: Organisation
    ) -> None:
        m = Membership.objects.get(user=volunteer)
        response = call(
            signed_in(volunteer),
            "patch",
            self.url(organisation, f"members/{m.pk}"),
            {"role": "owner"},
        )
        assert response.status_code == 403
        m.refresh_from_db()
        assert m.role == Role.VOLUNTEER

    def test_last_owner_cannot_step_down_or_leave(
        self, owner: User, organisation: Organisation
    ) -> None:
        m = Membership.objects.get(user=owner)
        client = signed_in(owner)
        path = self.url(organisation, f"members/{m.pk}")
        assert call(client, "patch", path, {"role": "volunteer"}).status_code == 409
        assert call(client, "delete", path).status_code == 409

    def test_volunteer_can_leave(self, volunteer: User, organisation: Organisation) -> None:
        m = Membership.objects.get(user=volunteer)
        path = self.url(organisation, f"members/{m.pk}")
        assert call(signed_in(volunteer), "delete", path).status_code == 204
        assert not Membership.objects.filter(pk=m.pk).exists()

    def test_volunteer_cannot_remove_others(
        self, owner: User, volunteer: User, organisation: Organisation
    ) -> None:
        m = Membership.objects.get(user=owner)
        path = self.url(organisation, f"members/{m.pk}")
        assert call(signed_in(volunteer), "delete", path).status_code == 403


class TestPairingCodes:
    def test_volunteer_issues_code(
        self, volunteer: User, event: Event, finish_line: TimingPoint
    ) -> None:
        response = call(
            signed_in(volunteer),
            "post",
            f"{API}/staff/events/{event.pk}/pairing-codes",
            {"timing_point_id": str(finish_line.pk)},
        )
        assert response.status_code == 201, response.content
        body = response.json()
        assert json.loads(body["qr_payload"])["code"] == body["code"]
        assert PairingCode.objects.get().timing_point == finish_line

    def test_outsider_cannot(self, event: Event) -> None:
        outsider = User.objects.create_user(email="x@example.com", password=PASSWORD)
        path = f"{API}/staff/events/{event.pk}/pairing-codes"
        assert call(signed_in(outsider), "post", path, {}).status_code == 404
        assert not PairingCode.objects.exists()


class TestInvitations:
    def invite(self, client: Client, organisation: Organisation, email: str, role: str) -> Any:
        return call(
            client,
            "post",
            f"{API}/staff/organisations/{organisation.slug}/invitations",
            {"email": email, "role": role},
        )

    def token_from_email(self) -> str:
        match = re.search(r"/invite/(\S+)", str(mail.outbox[-1].body))
        assert match
        return match.group(1)

    def test_invite_new_person_end_to_end(
        self,
        owner: User,
        organisation: Organisation,
        django_capture_on_commit_callbacks: Any,
    ) -> None:
        with django_capture_on_commit_callbacks(execute=True):
            response = self.invite(signed_in(owner), organisation, "New@Example.com", "volunteer")
        assert response.status_code == 201, response.content
        assert mail.outbox[0].to == ["new@example.com"]
        token = self.token_from_email()
        assert Invitation.objects.get().token_hash != token

        anon = Client()
        info = call(anon, "get", f"{API}/invitations/{token}").json()
        assert (info["organisation"], info["role"], info["has_account"]) == (
            organisation.name,
            "volunteer",
            False,
        )
        assert (
            call(anon, "post", f"{API}/invitations/{token}/accept", {"password": "x"}).status_code
            == 400
        )
        response = call(
            anon, "post", f"{API}/invitations/{token}/accept", {"password": PASSWORD, "name": "Nia"}
        )
        assert response.status_code == 201, response.content
        assert response.json()["account_created"] is True
        user = User.objects.get(email="new@example.com")
        assert user.check_password(PASSWORD) and user.name == "Nia"
        assert Membership.objects.get(user=user).role == Role.VOLUNTEER
        # The link works once.
        assert call(anon, "get", f"{API}/invitations/{token}").status_code == 404

        # They can now sign in through allauth and use the staff API.
        login = call(
            anon,
            "post",
            f"{AUTH}/browser/v1/auth/login",
            {"email": "new@example.com", "password": PASSWORD},
        )
        assert login.status_code == 200, login.content
        assert call(anon, "get", f"{API}/staff/me").json()["email"] == "new@example.com"

    def test_existing_account_must_sign_in(
        self, owner: User, organisation: Organisation, django_capture_on_commit_callbacks: Any
    ) -> None:
        other = Organisation.objects.create(name="Other club", slug="other")
        person = User.objects.create_user(email="p@example.com", password=PASSWORD)
        Membership.objects.create(user=owner, organisation=other, role=Role.OWNER)
        with django_capture_on_commit_callbacks(execute=True):
            self.invite(signed_in(owner), other, "p@example.com", "organiser")
        token = self.token_from_email()
        accept = f"{API}/invitations/{token}/accept"
        assert call(Client(), "post", accept, {}).status_code == 409
        assert call(signed_in(owner), "post", accept, {}).status_code == 403  # wrong person
        response = call(signed_in(person), "post", accept, {})
        assert response.status_code == 200
        assert Membership.objects.get(user=person, organisation=other).role == Role.ORGANISER

    def test_organiser_invites_only_volunteers(
        self, make_member: Callable[..., User], organisation: Organisation
    ) -> None:
        client = signed_in(make_member("org@example.com", Role.ORGANISER))
        assert self.invite(client, organisation, "a@example.com", "organiser").status_code == 403
        assert self.invite(client, organisation, "a@example.com", "volunteer").status_code == 201

    def test_volunteer_cannot_invite(self, volunteer: User, organisation: Organisation) -> None:
        response = self.invite(signed_in(volunteer), organisation, "a@example.com", "volunteer")
        assert response.status_code == 403

    def test_already_a_member(
        self, owner: User, volunteer: User, organisation: Organisation
    ) -> None:
        response = self.invite(signed_in(owner), organisation, volunteer.email.upper(), "volunteer")
        assert response.status_code == 409

    def test_bad_email(self, owner: User, organisation: Organisation) -> None:
        assert self.invite(signed_in(owner), organisation, "nope", "volunteer").status_code == 422

    def test_reinviting_replaces_the_old_link(
        self, owner: User, organisation: Organisation, django_capture_on_commit_callbacks: Any
    ) -> None:
        client = signed_in(owner)
        with django_capture_on_commit_callbacks(execute=True):
            self.invite(client, organisation, "a@example.com", "volunteer")
        first = self.token_from_email()
        with django_capture_on_commit_callbacks(execute=True):
            self.invite(client, organisation, "a@example.com", "volunteer")
        assert call(Client(), "get", f"{API}/invitations/{first}").status_code == 404
        assert Invitation.objects.count() == 1

    def test_expired(self, owner: User, organisation: Organisation) -> None:
        invitation, raw = Invitation.issue(organisation, "a@example.com", Role.VOLUNTEER, owner)
        invitation.expires_at = timezone.now() - timedelta(seconds=1)
        invitation.save()
        assert call(Client(), "get", f"{API}/invitations/{raw}").status_code == 404

    def test_list_and_cancel(self, owner: User, organisation: Organisation) -> None:
        invitation, _ = Invitation.issue(organisation, "a@example.com", Role.VOLUNTEER, owner)
        client = signed_in(owner)
        base = f"{API}/staff/organisations/{organisation.slug}/invitations"
        assert [i["email"] for i in call(client, "get", base).json()] == ["a@example.com"]
        assert call(client, "delete", f"{base}/{invitation.pk}").status_code == 204
        assert call(client, "get", base).json() == []

    def test_invite_never_demotes(self, owner: User, organisation: Organisation) -> None:
        _, raw = Invitation.issue(organisation, owner.email, Role.VOLUNTEER, None)
        response = call(signed_in(owner), "post", f"{API}/invitations/{raw}/accept", {})
        assert response.json()["role"] == "owner"


class TestSignIn:
    def test_open_sign_up_is_closed(self, client: Client) -> None:
        response = call(
            client,
            "post",
            f"{AUTH}/browser/v1/auth/signup",
            {"email": "a@example.com", "password": PASSWORD},
        )
        assert response.status_code == 403

    def test_totp_second_step(self, client: Client, organisation: Organisation) -> None:
        user = User.objects.create_user(email="org@example.com", password=PASSWORD)
        EmailAddress.objects.create(user=user, email=user.email, verified=True, primary=True)
        Membership.objects.create(user=user, organisation=organisation, role=Role.ORGANISER)
        secret = generate_totp_secret()
        TOTP.activate(user, secret)

        login = call(
            client,
            "post",
            f"{AUTH}/browser/v1/auth/login",
            {"email": user.email, "password": PASSWORD},
        )
        assert login.status_code == 401  # password alone isn't enough
        pending = [f["id"] for f in login.json()["data"]["flows"] if f.get("is_pending")]
        assert pending == ["mfa_authenticate"]
        assert call(client, "get", f"{API}/staff/me").status_code == 401

        code = format_hotp_value(hotp_value(secret, next(yield_hotp_counters_from_time())))
        done = call(client, "post", f"{AUTH}/browser/v1/auth/2fa/authenticate", {"code": code})
        assert done.status_code == 200, done.content
        assert call(client, "get", f"{API}/staff/me").json()["mfa_required"] is False

    def test_app_client_session_token(self, owner: User, organisation: Organisation) -> None:
        anon = Client()
        Authenticator.objects.filter(user=owner).delete()
        Membership.objects.filter(user=owner).update(role=Role.VOLUNTEER)
        login = call(
            anon, "post", f"{AUTH}/app/v1/auth/login", {"email": owner.email, "password": PASSWORD}
        )
        assert login.status_code == 200, login.content
        token = login.json()["meta"]["session_token"]
        me = call(Client(), "get", f"{API}/staff/me", **{"X-Session-Token": token})
        assert me.status_code == 200
        assert me.json()["email"] == owner.email
