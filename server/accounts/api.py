# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Staff API: who am I, organisation members and invitations (ADR 0002).

Signing in, passkeys, TOTP and password resets are allauth's headless API at /api/auth/.
"""

from datetime import datetime
from uuid import UUID

from allauth.account.models import EmailAddress
from allauth.headless.contrib.ninja.security import x_session_token_auth
from allauth.mfa.utils import is_mfa_enabled
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.core.validators import validate_email
from django.db import transaction
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import Router, Schema, Status
from ninja.errors import HttpError
from ninja.utils import check_csrf
from pydantic import field_validator

from accounts.models import ROLE_RANK, Invitation, Membership, Organisation, Role, User
from accounts.permissions import STAFF_AUTH, current_user, needs_mfa, require_role

router = Router(tags=["staff"], auth=STAFF_AUTH)
public_router = Router(tags=["invitations"])


class Error(Schema):
    detail: str
    code: str | None = None


class OrganisationRole(Schema):
    slug: str
    name: str
    role: Role


class MeOut(Schema):
    id: UUID
    email: str
    name: str
    mfa_enabled: bool
    mfa_required: bool  # an owner/organiser role without 2FA: the API is locked until set up
    organisations: list[OrganisationRole]


class MemberOut(Schema):
    id: UUID  # the membership
    user_id: UUID
    email: str
    name: str
    role: Role
    mfa_enabled: bool


class RoleIn(Schema):
    role: Role


class InvitationIn(Schema):
    email: str
    role: Role = Role.VOLUNTEER

    @field_validator("email")
    @classmethod
    def _valid_email(cls, value: str) -> str:
        value = value.strip().lower()
        try:
            validate_email(value)
        except ValidationError as e:
            raise ValueError("Enter a valid email address.") from e
        return value


class InvitationOut(Schema):
    id: UUID
    email: str
    role: Role
    expires_at: datetime
    invited_by: str | None


class InvitationInfo(Schema):
    organisation: str
    role: Role
    email: str
    has_account: bool


class AcceptIn(Schema):
    password: str | None = None  # only for a new account
    name: str = ""


class AcceptOut(Schema):
    organisation: str
    role: Role
    account_created: bool


# ------------------------------------------------------------------------------ me


@router.get("/me", response=MeOut, summary="The signed-in staff member and their roles")
def me(request: HttpRequest) -> MeOut:
    user = current_user(request)
    if user.is_superuser:
        roles = [(org, Role.OWNER) for org in Organisation.objects.all()]
    else:
        roles = [
            (m.organisation, Role(m.role))
            for m in user.memberships.select_related("organisation").order_by("organisation__name")
        ]
    return MeOut(
        id=user.pk,
        email=user.email,
        name=user.name,
        mfa_enabled=is_mfa_enabled(user),
        mfa_required=any(needs_mfa(user, role) for _, role in roles),
        organisations=[OrganisationRole(slug=o.slug, name=o.name, role=r) for o, r in roles],
    )


# --------------------------------------------------------------------------- members


def _organisation(slug: str) -> Organisation:
    return get_object_or_404(Organisation, slug=slug)


def _member_out(m: Membership) -> MemberOut:
    return MemberOut(
        id=m.pk,
        user_id=m.user_id,
        email=m.user.email,
        name=m.user.name,
        role=Role(m.role),
        mfa_enabled=is_mfa_enabled(m.user),
    )


def _check_not_last_owner(membership: Membership) -> None:
    if membership.role != Role.OWNER:
        return
    owners = Membership.objects.filter(organisation_id=membership.organisation_id, role=Role.OWNER)
    if owners.count() <= 1:
        raise HttpError(
            409, "An organisation needs at least one owner. Make someone else owner first."
        )


@router.get(
    "/organisations/{slug}/members",
    response={200: list[MemberOut], 403: Error, 404: Error},
    summary="List members (any role)",
)
def list_members(request: HttpRequest, slug: str) -> list[MemberOut]:
    organisation = _organisation(slug)
    require_role(request, organisation, Role.VOLUNTEER)
    members = organisation.memberships.select_related("user").order_by("user__email")
    return [_member_out(m) for m in members]


@router.patch(
    "/organisations/{slug}/members/{membership_id}",
    response={200: MemberOut, 403: Error, 404: Error, 409: Error},
    summary="Change a member's role (owners)",
)
def change_role(request: HttpRequest, slug: str, membership_id: UUID, payload: RoleIn) -> MemberOut:
    organisation = _organisation(slug)
    require_role(request, organisation, Role.OWNER)
    with transaction.atomic():
        membership = get_object_or_404(
            Membership.objects.select_for_update().select_related("user"),
            pk=membership_id,
            organisation=organisation,
        )
        if payload.role != Role.OWNER:
            _check_not_last_owner(membership)
        membership.role = payload.role
        membership.save(update_fields=["role", "updated_at"])
    return _member_out(membership)


@router.delete(
    "/organisations/{slug}/members/{membership_id}",
    response={204: None, 403: Error, 404: Error, 409: Error},
    summary="Remove a member (owners), or leave (yourself)",
)
def remove_member(request: HttpRequest, slug: str, membership_id: UUID) -> Status[None]:
    organisation = _organisation(slug)
    membership = get_object_or_404(Membership, pk=membership_id, organisation=organisation)
    leaving = membership.user_id == current_user(request).pk
    require_role(request, organisation, Role.VOLUNTEER if leaving else Role.OWNER)
    with transaction.atomic():
        _check_not_last_owner(Membership.objects.select_for_update().get(pk=membership.pk))
        membership.delete()
    return Status(204, None)


# ----------------------------------------------------------------------- invitations


def _invitation_out(i: Invitation) -> InvitationOut:
    return InvitationOut(
        id=i.pk,
        email=i.email,
        role=Role(i.role),
        expires_at=i.expires_at,
        invited_by=i.invited_by.email if i.invited_by else None,
    )


def _send_invitation(invitation: Invitation, raw: str, inviter: User) -> None:
    link = f"{settings.WEB_URL}/invite/{raw}"
    send_mail(
        subject=f"Join {invitation.organisation.name} on Race Timing",
        message=(
            f"{inviter} has invited you to help run timing for "
            f"{invitation.organisation.name} as {invitation.get_role_display().lower()}.\n\n"
            f"Accept the invitation here:\n{link}\n\n"
            f"The link works once and expires on {invitation.expires_at:%d %B %Y}. "
            "If you weren't expecting this, you can ignore it."
        ),
        from_email=None,
        recipient_list=[invitation.email],
    )


@router.get(
    "/organisations/{slug}/invitations",
    response={200: list[InvitationOut], 403: Error, 404: Error},
    summary="List pending invitations (organisers and owners)",
)
def list_invitations(request: HttpRequest, slug: str) -> list[InvitationOut]:
    organisation = _organisation(slug)
    require_role(request, organisation, Role.ORGANISER)
    pending = organisation.invitations.pending().select_related("invited_by")
    return [_invitation_out(i) for i in pending]


@router.post(
    "/organisations/{slug}/invitations",
    response={201: InvitationOut, 403: Error, 404: Error, 409: Error},
    summary="Invite someone by email (organisers invite volunteers; owners invite anyone)",
)
def invite(request: HttpRequest, slug: str, payload: InvitationIn) -> Status[InvitationOut]:
    organisation = _organisation(slug)
    role = require_role(request, organisation, Role.ORGANISER)
    if role != Role.OWNER and payload.role != Role.VOLUNTEER:
        raise HttpError(403, "Only owners can invite organisers and owners.")
    email = payload.email
    if Membership.objects.filter(organisation=organisation, user__email__iexact=email).exists():
        raise HttpError(409, "They're already a member.")
    inviter = current_user(request)
    with transaction.atomic():
        # A new invite replaces any earlier one, so only the latest link works.
        organisation.invitations.filter(email=email, accepted_at__isnull=True).delete()
        invitation, raw = Invitation.issue(organisation, email, payload.role, inviter)
        transaction.on_commit(lambda: _send_invitation(invitation, raw, inviter))
    return Status(201, _invitation_out(invitation))


@router.delete(
    "/organisations/{slug}/invitations/{invitation_id}",
    response={204: None, 403: Error, 404: Error},
    summary="Cancel a pending invitation (organisers and owners)",
)
def cancel_invitation(request: HttpRequest, slug: str, invitation_id: UUID) -> Status[None]:
    organisation = _organisation(slug)
    require_role(request, organisation, Role.ORGANISER)
    get_object_or_404(organisation.invitations.pending(), pk=invitation_id).delete()
    return Status(204, None)


# ------------------------------------------------------------- accepting (public)


def _pending(token: str) -> Invitation:
    invitation = Invitation.find_pending(token)
    if invitation is None:
        raise HttpError(404, "This invitation link is wrong, used or expired.")
    return invitation


def _signed_in(request: HttpRequest) -> User | None:
    if request.headers.get("X-Session-Token"):
        user = x_session_token_auth(request)
        return user if isinstance(user, User) else None
    if request.user.is_authenticated:
        if check_csrf(request):
            raise HttpError(403, "CSRF check failed.")
        return current_user(request)
    return None


@public_router.get(
    "/{token}",
    response={200: InvitationInfo, 404: Error},
    summary="What an invitation is for (shown before accepting)",
)
def invitation_info(request: HttpRequest, token: str) -> InvitationInfo:
    invitation = _pending(token)
    return InvitationInfo(
        organisation=invitation.organisation.name,
        role=Role(invitation.role),
        email=invitation.email,
        has_account=User.objects.filter(email__iexact=invitation.email).exists(),
    )


@public_router.post(
    "/{token}/accept",
    response={200: AcceptOut, 201: AcceptOut, 400: Error, 403: Error, 404: Error, 409: Error},
    summary="Accept an invitation, creating an account if the address doesn't have one",
)
def accept_invitation(request: HttpRequest, token: str, payload: AcceptIn) -> Status[AcceptOut]:
    with transaction.atomic():
        invitation = _pending(token)
        invitation = Invitation.objects.select_for_update().get(pk=invitation.pk)
        if invitation.accepted_at is not None:
            raise HttpError(404, "This invitation link is wrong, used or expired.")
        existing = User.objects.filter(email__iexact=invitation.email).first()
        signed_in = _signed_in(request)
        if signed_in is not None and (existing is None or signed_in.pk != existing.pk):
            raise HttpError(
                403, "This invitation is for a different email address. Sign out first."
            )
        created = existing is None
        if existing is None:
            user = _create_account(invitation.email, payload)
        elif signed_in is None:
            raise HttpError(409, "You already have an account: sign in, then accept.")
        else:
            user = existing
        membership, _ = Membership.objects.get_or_create(
            user=user, organisation=invitation.organisation, defaults={"role": invitation.role}
        )
        if ROLE_RANK[Role(invitation.role)] > ROLE_RANK[Role(membership.role)]:
            membership.role = invitation.role  # an invite can promote, never demote
            membership.save(update_fields=["role", "updated_at"])
        invitation.accepted_at = timezone.now()
        invitation.accepted_by = user
        invitation.save(update_fields=["accepted_at", "accepted_by", "updated_at"])
    out = AcceptOut(
        organisation=invitation.organisation.slug,
        role=Role(membership.role),
        account_created=created,
    )
    return Status(201 if created else 200, out)


def _create_account(email: str, payload: AcceptIn) -> User:
    if not payload.password:
        raise HttpError(400, "Choose a password for your new account.")
    candidate = User(email=email, name=payload.name.strip())
    try:
        validate_password(payload.password, user=candidate)
    except ValidationError as e:
        raise HttpError(400, " ".join(e.messages)) from e
    user = User.objects.create_user(email=email, password=payload.password, name=candidate.name)
    # The invite link reached this inbox, which proves the address.
    EmailAddress.objects.create(user=user, email=email, verified=True, primary=True)
    return user
