#  running/app/admin.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
#  used for creating admin permissions
from django.contrib import admin

#  used for admin record management
from .models import (
    Race,
    Participant,
    RaceResult,
    Profile,
    ParticipantCategory,
    RaceCategory,
    CustomUser,
    Image,
    OrganiserApplication
)

# -------------------- Inline for Participants within Race --------------------
class ParticipantInline(admin.TabularInline):
    model = Participant
    extra = 0

# ------------------------------------------------- Class Declarations -------------------------------------------------
# -------------------- Race Admin --------------------
@admin.register(Race)
class RaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'date', 'start_time', 'is_completed')
    list_filter = ('date', 'is_completed', 'race_category')
    search_fields = ('name', 'address')
    filter_horizontal = ('participant_categories', 'organiser', 'participants')
    inlines = [ParticipantInline]


# -------------------- Participant Admin --------------------
@admin.register(Participant)
class ParticipantAdmin(admin.ModelAdmin):
    list_display = ('name', 'race', 'race_number', 'age', 'gender', 'club_name', 'team_name', 'status')
    list_filter = ('race', 'gender', 'status')
    search_fields = ('name', 'race_number', 'club_name', 'team_name')
    autocomplete_fields = ['race', 'user']


# -------------------- Race Result Admin --------------------
@admin.register(RaceResult)
class RaceResultAdmin(admin.ModelAdmin):
    list_display = ('participant', 'race', 'total_time')
    list_filter = ('race',)
    search_fields = ('participant__name',)


# -------------------- Profile Admin --------------------
@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'notify_race_updates')


# -------------------- Participant Category Admin --------------------
@admin.register(ParticipantCategory)
class ParticipantCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# -------------------- Race Category Admin --------------------
@admin.register(RaceCategory)
class RaceCategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name',)


# -------------------- Image Admin --------------------
@admin.register(Image)
class ImageAdmin(admin.ModelAdmin):
    list_display = ('name', 'race', 'timestamp')
    list_filter = ('race', 'timestamp')
    search_fields = ('name',)


# -------------------- Organiser Application Admin --------------------
@admin.register(OrganiserApplication)
class OrganiserApplicationAdmin(admin.ModelAdmin):
    list_display = ('user', 'race', 'status', 'created_at')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'race__name')
    autocomplete_fields = ['user', 'race']


# -------------------- Custom User Admin (Optional) --------------------
@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = ('username', 'email', 'name', 'is_staff', 'is_superuser', 'mfa_enabled')
    search_fields = ('username', 'email', 'name')
    list_filter = ('is_staff', 'is_superuser', 'mfa_enabled')
