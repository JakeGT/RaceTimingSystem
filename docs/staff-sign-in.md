# Staff sign-in and roles

How organisers and volunteers get accounts and what each role can do ([ADR 0002](decisions/0002-event-mode-and-accounts.md)). Runners have no accounts.

## Getting an account

There's no open sign-up. The first account on an install comes from `manage.py createsuperuser`. Everyone else joins by invitation:

1. An owner or organiser calls `POST /api/v1/staff/organisations/{slug}/invitations` with an email and a role. The server emails a one-use link, `{WEB_URL}/invite/{token}`, that expires after 7 days. Inviting the same address again replaces the old link.
2. The web app shows what the invite is for with `GET /api/v1/invitations/{token}`.
3. `POST /api/v1/invitations/{token}/accept`:
   - **New address:** send `{"password": ..., "name": ...}`. The account is created with its email already verified (the link proves it), and the response is `201`. Then sign in as below.
   - **Existing account:** sign in first, then accept with an empty body (`200`). Accepting while signed in as someone else is refused.
   - Accepting can promote an existing member, never demote them.

## Signing in

Sign-in, passkeys, TOTP, recovery codes and password resets are [django-allauth's headless API](https://docs.allauth.org/en/latest/headless/openapi-specification/) at `/api/auth/`:

- **Browser** (the React app, same origin): `/api/auth/browser/v1/...`, with the session cookie and CSRF token.
- **App** (anything else): `/api/auth/app/v1/...`. The login response carries `meta.session_token`; send it as `X-Session-Token` on every request.

When an account has 2FA, logging in with a password answers `401` with a pending `mfa_authenticate` flow; finish it with `POST .../auth/2fa/authenticate`. Passkeys can also sign in on their own.

## Roles

| | Volunteer | Organiser | Owner |
|---|---|---|---|
| See members, pair phones (`POST /api/v1/staff/events/{id}/pairing-codes`) | ✓ | ✓ | ✓ |
| Invite volunteers, see and cancel invitations | | ✓ | ✓ |
| Invite organisers and owners, change roles, remove members | | | ✓ |
| Needs 2FA (passkey or authenticator app) | | ✓ | ✓ |

- Anyone can leave an organisation, except its last owner.
- Superusers count as owners of every organisation.
- Someone outside an organisation gets `404` for everything in it, so the API doesn't reveal what exists.
- **2FA is enforced by the API:** an owner or organiser without a passkey or TOTP gets `403` with `"code": "mfa_required"` from every staff endpoint until they set one up. `GET /api/v1/staff/me` returns `mfa_required: true` so the web app can send them straight to set-up.

## Known gaps

- **Django admin** still signs in with a password only. It's a stopgap for install operators until the organiser console (Phase 4); restrict who has `is_staff`.
- **Passkeys** only work on the domain they were created on, and on `https` or `localhost`. Plain-http development sets `MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN` from `DEBUG`. Venue laptops use QR-paired browser sessions instead (Phase 6).
