# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
"""Django settings. Everything environment-specific comes from env vars (see .env.example)."""

from pathlib import Path

import django_stubs_ext
import environ

# Lets admin/form classes be subscripted at runtime (e.g. ModelAdmin[Event]) for mypy.
django_stubs_ext.monkeypatch()

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CSRF_TRUSTED_ORIGINS=(list, []),
)
environ.Env.read_env(BASE_DIR / ".env", overwrite=False)

SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env("CSRF_TRUSTED_ORIGINS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "core",
    "accounts",
    "events",
    "timing",
    "results",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.headless",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",  # Django admin's login form
    "allauth.account.auth_backends.AuthenticationBackend",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# Postgres in the cloud, SQLite on a venue laptop (ADR 0002). Core models must work on both.
DATABASES = {"default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")}
if DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3":
    DATABASES["default"].setdefault("OPTIONS", {})
    DATABASES["default"]["OPTIONS"].setdefault(
        "init_command", "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;"
    )

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "UTC"  # Store and compute in UTC; each Event carries its own display timezone.
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Uploaded crops are personal data: never served publicly. Organiser views stream them
# after a permission check (slice 1.4+).
MEDIA_ROOT = env.path("MEDIA_ROOT", default=BASE_DIR / "media")
STATIC_ROOT = BASE_DIR / "staticfiles"

# ------------------------------------------------------------------ staff sign-in (ADR 0002)
# The React app's address: links in emails (invites, password resets) point here.
WEB_URL = env("WEB_URL", default="http://localhost:5173").rstrip("/")

# EMAIL_URL (e.g. smtp+tls://user:pass@host:587) becomes Django 6.1's MAILERS setting.
_email = env.email_url("EMAIL_URL", default="consolemail://")
_email_options = {
    "host": _email.get("EMAIL_HOST"),
    "port": _email.get("EMAIL_PORT"),
    "username": _email.get("EMAIL_HOST_USER"),
    "password": _email.get("EMAIL_HOST_PASSWORD"),
    "use_tls": _email.get("EMAIL_USE_TLS"),
    "use_ssl": _email.get("EMAIL_USE_SSL"),
}
MAILERS = {
    "default": {
        "BACKEND": _email["EMAIL_BACKEND"],
        "OPTIONS": {k: v for k, v in _email_options.items() if v not in (None, "", False)},
    }
}
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Race Timing <timing@localhost>")

# django-allauth, headless only: the React app (or the venue laptop's UI) draws the forms.
# Accounts are created only by accepting an invite (accounts.api), never by open sign-up.
HEADLESS_ONLY = True
HEADLESS_CLIENTS = ("browser", "app")
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{WEB_URL}/account/verify-email/{{key}}",
    "account_reset_password": f"{WEB_URL}/account/password/reset",
    "account_reset_password_from_key": f"{WEB_URL}/account/password/reset/key/{{key}}",
    "account_signup": f"{WEB_URL}/account/signup-closed",
}
ACCOUNT_ADAPTER = "accounts.adapter.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_PASSWORD_RESET = False
ACCOUNT_PREVENT_ENUMERATION = True
MFA_SUPPORTED_TYPES = ["totp", "recovery_codes", "webauthn"]
MFA_PASSKEY_LOGIN_ENABLED = True
MFA_TOTP_ISSUER = env("MFA_TOTP_ISSUER", default="Race Timing")
# Browsers only allow WebAuthn on https or localhost; this lets plain-http dev work.
MFA_WEBAUTHN_ALLOW_INSECURE_ORIGIN = DEBUG

# Models subclass common.models.UUIDModel; this only affects third-party apps.
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
