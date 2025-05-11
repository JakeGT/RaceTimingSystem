from django.urls import path
from .views import auth_views
from rest_framework.response import Response
from rest_framework import status
from rest_framework_simplejwt.views import TokenRefreshView
from .views.category_views import get_categories
from .views.race_views import create_race, get_my_races, update_race, get_all_races


class DebugTokenRefreshView(TokenRefreshView):
    def post(self, request, *args, **kwargs):
        refresh_token = request.COOKIES.get("refresh_token")

        if not refresh_token:
            return Response({"error": "No refresh token provided."}, status=status.HTTP_400_BAD_REQUEST)

        request.data['refresh'] = refresh_token
        return super().post(request, *args, **kwargs)


urlpatterns = [
    path('api/register/', auth_views.api_register, name='api_register'),
    path('api/login/', auth_views.api_login, name='api_login'),
    path('api/logout', auth_views.logout_view, name='logout'),
    path('api/csrf/', auth_views.get_csrf_token, name='get_csrf_token'),
    path('api/token/refresh/', DebugTokenRefreshView.as_view(), name='token_refresh'),
    path('api/categories/', get_categories, name='get_categories'),
    path('api/create-race/', create_race, name='create_race'),
    path('api/races/my/', get_my_races, name="get_my_races"),
    path('api/races/<int:race_id>/update/', update_race, name="update_race"),
    path('api/races/all', get_all_races, name="get_all_races"),
]

