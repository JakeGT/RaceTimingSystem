#  running/app/urls.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.contrib import admin
from django.urls import path, include
from . import views
from django.contrib.auth import views as auth_views

#  define url patterns
urlpatterns = [

    #  landing page
    path('', views.landing_page, name='landing'),

    #  dashboard page
    path('dashboard/', views.dashboard, name='dashboard'),

    #  race configuration page
    path('race-config/', views.race_config, name='race_config'),

    #  participants page
    path('upload-participants/', views.upload_participants, name='upload_participants'),

    #  manual results upload page
    path('upload-results/', views.upload_results, name='upload_results'),

    path('register/', views.user_register, name='register'),

    path('login/', views.user_login, name='login'),

    path('password-reset/', views.password_reset_request, name='password-reset'),

    path('logout/', views.user_logout, name='logout'),

    path('register_for_race/', views.register_for_race, name='register_for_race'),
    path('manage_participants/<int:race_id>/', views.manage_participants, name='manage_participants'),

    path('register-race/', views.register_for_race, name='register_for_race'),

    path('race-history/', views.race_history, name='race_history'),

    path('race-results/<int:race_id>/', views.race_results, name='race_results'),

    path('organiser-approval/', views.race_organiser_dashboard, name='race_organiser_dashboard'),

    path('race/<int:race_id>/', views.race_detail, name='race_detail'),

    path('upcoming-races', views.upcoming_races, name='upcoming_races'),
]
