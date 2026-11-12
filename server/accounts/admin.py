# SPDX-FileCopyrightText: 2026 Race Timing System contributors
# SPDX-License-Identifier: AGPL-3.0-or-later
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import BaseUserCreationForm, UserChangeForm

from accounts.models import Membership, Organisation, User


class UserCreationForm(BaseUserCreationForm[User]):
    class Meta:
        model = User
        fields = ("email", "name")


class EmailUserChangeForm(UserChangeForm[User]):
    class Meta:
        model = User
        fields = "__all__"


class MembershipInline(admin.TabularInline[Membership, Organisation]):
    model = Membership
    extra = 0
    autocomplete_fields = ("user",)


@admin.register(User)
class UserAdmin(BaseUserAdmin[User]):
    form = EmailUserChangeForm
    add_form = UserCreationForm
    ordering = ("email",)
    list_display = ("email", "name", "is_staff", "is_active", "last_login")
    search_fields = ("email", "name")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("name",)}),
        (
            "Permissions",
            {
                "fields": (
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "name", "password1", "password2"),
            },
        ),
    )


@admin.register(Organisation)
class OrganisationAdmin(admin.ModelAdmin[Organisation]):
    list_display = ("name", "slug", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}  # noqa: RUF012
    inlines = (MembershipInline,)
