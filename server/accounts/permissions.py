# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Who can do what in the staff API (ADR 0002).

Roles rank volunteer < organiser < owner, and every check is "at least this role" in
the organisation that owns the thing. Owners and organisers must have 2FA (a passkey
or TOTP) set up before they can use the API at all; until then every call answers
403 with `"code": "mfa_required"` so the web app can send them to set it up.
"""

from typing import cast

from allauth.headless.contrib.ninja.security import x_session_token_auth
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.http import HttpRequest
from ninja.errors import HttpError
from ninja.security import SessionAuth

from accounts.models import ROLE_RANK, Membership, Organisation, Role, User

ROLES_NEEDING_MFA = frozenset({Role.OWNER, Role.ORGANISER})


class BrowserSessionAuth(SessionAuth):
    """The web app's session cookie (allauth's "browser" client). CSRF is only checked
    when there's a session cookie, so a request from an app client that sends no
    cookie falls through to the next auth class instead of failing the CSRF check."""

    def _get_key(self, request: HttpRequest) -> str | None:
        if settings.SESSION_COOKIE_NAME not in request.COOKIES:
            return None
        return super()._get_key(request)


# allauth's "app" client (X-Session-Token header) first, then the browser session.
STAFF_AUTH = [x_session_token_auth, BrowserSessionAuth()]


class MfaRequired(Exception):
    def __init__(self) -> None:
        super().__init__("Set up a passkey or an authenticator app to use this role.")


def current_user(request: HttpRequest) -> User:
    return cast(User, request.user)


def needs_mfa(user: User, role: Role) -> bool:
    return role in ROLES_NEEDING_MFA and not is_mfa_enabled(user)


def role_in(user: User, organisation: Organisation) -> Role | None:
    """The user's role, or None. Superusers run the install, so they're owners everywhere."""
    if user.is_superuser:
        return Role.OWNER
    role = (
        Membership.objects.filter(user=user, organisation=organisation)
        .values_list("role", flat=True)
        .first()
    )
    return Role(role) if role else None


def require_role(request: HttpRequest, organisation: Organisation, minimum: Role) -> Role:
    """Check the signed-in user has at least `minimum` in the organisation.

    Not being a member at all is a 404, so the API doesn't reveal which organisations
    and events exist to people outside them.
    """
    user = current_user(request)
    role = role_in(user, organisation)
    if role is None:
        raise HttpError(404, "Not found.")
    if needs_mfa(user, role):
        raise MfaRequired
    if ROLE_RANK[role] < ROLE_RANK[minimum]:
        raise HttpError(403, f"This needs the {minimum.label.lower()} role or higher.")
    return role


def outranks_or_equals(role: Role, other: str) -> bool:
    return ROLE_RANK[role] >= ROLE_RANK[Role(other)]


__all__ = [
    "STAFF_AUTH",
    "MfaRequired",
    "current_user",
    "needs_mfa",
    "require_role",
    "role_in",
]
