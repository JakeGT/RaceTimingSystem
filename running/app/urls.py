#  running/app/urls.py

# -------------------------------------------------- Import Libraries --------------------------------------------------
from django.urls import path
from . import views

#  define url patterns
urlpatterns = [

    #  landing page
    path('', views.dashboard, name='dashboard'),

    #  race configuration page
    path('race-config/', views.race_config, name='race_config'),

    #  participants page
    path('upload-participants/', views.upload_participants, name='upload_participants'),

    #  manual results upload page
    path('upload-results/', views.upload_results, name='upload_results'),
]
