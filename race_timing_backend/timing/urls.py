from django.urls import path
from . import api_views

urlpatterns = [
    path('api/register/', api_views.api_register, name='api_register'),
    path('api/login/', api_views.api_login, name='api_login'),
]

