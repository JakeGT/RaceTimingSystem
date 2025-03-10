#  running/app/urls.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from . import views
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from django.urls import path, include
from .views import upload_json
from django.urls import path
from .views import CustomPasswordResetView
from django.contrib.auth import views as auth_views

# -------------------------------------------------- Define URL Patterns --------------------------------------------------
urlpatterns = [

    # upload json of data
    path('race/<int:race_id>/upload/', upload_json, name='upload_json'),

    #  landing page
    path('', views.landing_page, name='landing'),

    #  dashboard page
    path('dashboard/', views.dashboard, name='dashboard'),

    #  race configuration page
    path('race-config/', views.race_config, name='race_config'),

    #  participants upload page
    path('upload-participants/', views.upload_participants, name='upload_participants'),

    #  results upload page
    path('upload-results/', views.upload_results, name='upload_results'),

    #  user registration page
    path('register/', views.user_register, name='register'),

    #  user login page
    path('login/', views.user_login, name='login'),

    path("password_reset/", CustomPasswordResetView.as_view(), name="password_reset"),
    path("password_reset/done/", auth_views.PasswordResetDoneView.as_view(template_name="app/password_reset_done.html"),
         name="password_reset_done"),
    path("reset/<uidb64>/<token>/",
         auth_views.PasswordResetConfirmView.as_view(template_name="app/password_reset_confirm.html"),
         name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(template_name="app/password_reset_complete.html"),
         name="password_reset_complete"),
    #  user logout route
    path('logout/', views.user_logout, name='logout'),

    #  organiser management page
    path('manage_participants/<int:race_id>/', views.manage_participants, name='manage_participants'),

    #  registering for races page
    path('register-race/', views.register_for_race, name='register_for_race'),

    #  race history page
    path('race-history/', views.race_history, name='race_history'),

    #  organiser dashboard page
    path('organiser-dashboard/', views.race_organiser_dashboard, name='race_organiser_dashboard'),

    #  race details page, including leaderboard
    path('race/<int:race_id>/', views.race_detail, name='race_detail'),

    #  upcoming races page
    path('upcoming-races', views.upcoming_races, name='upcoming_races'),

    #  user settings page
    path('settings', views.settings_view, name='settings'),

    #  user logged in password change pages
    path('accounts/password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),

    #  successful password reset page
    path('accounts/password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),

    #  user profile page
    path("profile/", views.profile_view, name="profile"),

    #  organiser race view page
    path('organiser/race/<int:race_id>/', views.organiser_race_detail, name='organiser_race_detail'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
