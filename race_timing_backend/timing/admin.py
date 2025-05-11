from django.contrib import admin

# Register your models here.

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, Race, OrganiserApplication, RaceResult, Participant



@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    filter_horizontal = ("participants", "participant_categories")
    list_display = ("name", "start_datetime", "is_completed")
    list_filter = ("is_completed", "start_datetime")
    search_fields = ("name",)

@admin.register(OrganiserApplication)
class OrganiserApplicationAdmin(admin.ModelAdmin):
    list_display = ("user", "race", "status", "created_at", "reviewed_at", "approved_by")
    list_filter = ("status", "created_at")
    search_fields = ("user__username", "race__name")
    readonly_fields = ("created_at", "reviewed_at", "approved_by")

    actions = ["approve_applications", "deny_applications"]

    def approve_applications(self, request, queryset):
        for application in queryset.filter(status="pending"):
            application.approve(approver=request.user, comment="Approved via admin")
        self.message_user(request, "Selected applications approved.")

    def deny_applications(self, request, queryset):
        for application in queryset.filter(status="pending"):
            application.deny(approver=request.user, comment="Denied via admin")
        self.message_user(request, "Selected applications denied.")

    approve_applications.short_description = "Approve selected applications"
    deny_applications.short_description = "Deny selected applications"

@admin.register(RaceResult)
class RaceResultAdmin(admin.ModelAdmin):
    list_display = (
        "participant_display",
        "race",
        "position",
        "total_time",
        "finish_time",
        "disqualified",
    )
    list_filter = ("race", "disqualified")
    search_fields = ("participant__first_name", "participant__last_name", "race__name")
    ordering = ("race", "position")
    autocomplete_fields = ("participant", "race")

    def participant_display(self, obj):
        return f"{obj.participant.first_name} {obj.participant.last_name}"
    participant_display.short_description = "Participant"

@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    search_fields = ("first_name", "last_name")

class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ("username", "email", "first_name", "last_name", "is_runner", "is_organiser")
    list_filter = ('is_runner', 'is_organiser', 'is_staff', 'is_superuser')
    fieldsets = UserAdmin.fieldsets + (
        (None, {'fields': ('is_runner', 'is_organiser')}),
    )
    add_fieldsets = UserAdmin.add_fieldsets + (
        (None, {'fields': ('is_runner', 'is_organiser')}),
    )
    search_fields = ('username', 'email')
    ordering = ('username',)


admin.site.register(CustomUser, CustomUserAdmin)
