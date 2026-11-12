# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Staff accounts and organisations. Runners don't have accounts in v1 (ADR 0002)."""

import secrets
import uuid
from datetime import timedelta
from typing import Any, ClassVar

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone

from common.models import UUIDModel
from common.secrets import hash_secret


class UserManager(BaseUserManager["User"]):
    use_in_migrations = True

    def _create_user(self, email: str, password: str | None, **extra: Any) -> "User":
        if not email:
            raise ValueError("An email address is required")
        user = self.model(email=self.normalize_email(email), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email: str, password: str | None = None, **extra: Any) -> "User":
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email: str, password: str | None = None, **extra: Any) -> "User":
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        if extra["is_staff"] is not True or extra["is_superuser"] is not True:
            raise ValueError("A superuser must have is_staff=True and is_superuser=True")
        return self._create_user(email, password, **extra)


class User(AbstractUser):
    """A staff member (organiser or volunteer). Signs in with their email address."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid7, editable=False)
    username = None  # type: ignore[assignment]
    first_name = None  # type: ignore[assignment]
    last_name = None  # type: ignore[assignment]
    email = models.EmailField("email address", unique=True)
    # One name field: works for every naming convention, and it's only used for display.
    name = models.CharField(max_length=150, blank=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: ClassVar[list[str]] = []

    objects: ClassVar[UserManager] = UserManager()  # type: ignore[assignment]

    def __str__(self) -> str:
        return self.name or self.email

    def get_full_name(self) -> str:
        return self.name

    def get_short_name(self) -> str:
        return self.name or self.email


class Organisation(UUIDModel):
    """A club or race organiser. One install hosts many (ADR 0002)."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=80, unique=True)
    members = models.ManyToManyField(User, through="Membership", related_name="organisations")

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return self.name


class Role(models.TextChoices):
    OWNER = "owner", "Owner"
    ORGANISER = "organiser", "Organiser"
    VOLUNTEER = "volunteer", "Volunteer"


class Membership(UUIDModel):
    """A user's role in an organisation.

    Owners manage members and settings, organisers manage events, and volunteers can
    run devices and work the review queue but can't change an event's set-up.
    """

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="memberships")
    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="memberships"
    )
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VOLUNTEER)

    class Meta:
        constraints = (
            models.UniqueConstraint(
                fields=("user", "organisation"), name="unique_membership_per_organisation"
            ),
        )

    def __str__(self) -> str:
        return f"{self.user} - {self.organisation} ({self.get_role_display()})"


ROLE_RANK = {Role.VOLUNTEER: 1, Role.ORGANISER: 2, Role.OWNER: 3}
INVITE_LIFETIME = timedelta(days=7)


class InvitationQuerySet(models.QuerySet["Invitation"]):
    def pending(self) -> "InvitationQuerySet":
        return self.filter(accepted_at__isnull=True, expires_at__gt=timezone.now())


class Invitation(UUIDModel):
    r"""An emailed link that lets someone join an organisation with a role.

    Only a hash of the link's token is stored. Accepting an invite is the only way to
    get an account (apart from \`createsuperuser\`), and doing so proves the email
    address, because the link was sent there.
    """

    organisation = models.ForeignKey(
        Organisation, on_delete=models.CASCADE, related_name="invitations"
    )
    email = models.EmailField()
    role = models.CharField(max_length=16, choices=Role.choices, default=Role.VOLUNTEER)
    token_hash = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    expires_at = models.DateTimeField()
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    objects = InvitationQuerySet.as_manager()

    class Meta:
        ordering = ("-created_at",)

    def __str__(self) -> str:
        return f"{self.email} to {self.organisation} as {self.get_role_display()}"

    @classmethod
    def issue(
        cls, organisation: Organisation, email: str, role: str, invited_by: User | None
    ) -> tuple["Invitation", str]:
        """Create an invite and return it with the raw token (shown once, in the email)."""
        raw = secrets.token_urlsafe(32)
        invitation = cls.objects.create(
            organisation=organisation,
            email=UserManager.normalize_email(email).lower(),
            role=role,
            token_hash=hash_secret(raw),
            invited_by=invited_by,
            expires_at=timezone.now() + INVITE_LIFETIME,
        )
        return invitation, raw

    @classmethod
    def find_pending(cls, raw: str) -> "Invitation | None":
        return (
            cls.objects.pending()
            .select_related("organisation")
            .filter(token_hash=hash_secret(raw))
            .first()
        )
