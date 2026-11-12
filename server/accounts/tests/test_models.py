# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
import uuid

import pytest
from django.contrib.auth import authenticate
from django.db import IntegrityError

from accounts.models import Membership, Organisation, Role, User


@pytest.mark.django_db
class TestUser:
    def test_email_is_the_login(self) -> None:
        User.objects.create_user(email="Alex@Example.COM", password="a-long-passphrase")
        # The domain part is normalised to lower case; the local part is kept as typed.
        user = authenticate(email="Alex@example.com", password="a-long-passphrase")
        assert user is not None
        assert user.get_short_name() == "Alex@example.com"

    def test_email_required(self) -> None:
        with pytest.raises(ValueError, match="email"):
            User.objects.create_user(email="", password="x")

    def test_superuser_flags(self) -> None:
        admin = User.objects.create_superuser(email="root@example.com", password="x")
        assert admin.is_staff and admin.is_superuser

    def test_ids_are_uuid7(self) -> None:
        user = User.objects.create_user(email="a@example.com")
        assert isinstance(user.pk, uuid.UUID) and user.pk.version == 7


@pytest.mark.django_db
class TestOrganisation:
    def test_uuid7_ids_sort_by_creation(self) -> None:
        first = Organisation.objects.create(name="A", slug="a")
        second = Organisation.objects.create(name="B", slug="b")
        assert first.pk.version == 7
        assert first.pk < second.pk

    def test_one_membership_per_user_and_organisation(self, organisation: Organisation) -> None:
        user = User.objects.create_user(email="v@example.com")
        Membership.objects.create(user=user, organisation=organisation, role=Role.VOLUNTEER)
        with pytest.raises(IntegrityError):
            Membership.objects.create(user=user, organisation=organisation, role=Role.OWNER)
