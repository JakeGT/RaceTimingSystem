#  running/app/urls.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.contrib import admin
from django.urls import path, include
from . import views

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
]
