# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Staff accounts and organisations. Runners don't have accounts in v1 (ADR 0002)."""

import uuid
from typing import Any, ClassVar

from common.models import UUIDModel
from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractUser
from django.db import models


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
