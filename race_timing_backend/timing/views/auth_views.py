from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.views.decorators.csrf import ensure_csrf_cookie
from ..serializers.user_serializers import UserSerializer

#TODO: Logging

def set_refresh_cookie(response, token):
    response.set_cookie(
        key='refresh_token',
        value=str(token),
        httponly=True,
        secure=False, # TODO: Update to True in Prod
        samesite='Lax',
        path="/api/token/refresh",
        max_age=60 * 60 * 24 * 7,
    )


@api_view(['POST'])
def api_register(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        response = Response({
            'detail': 'User registered successfully',
            'access': str(refresh.access_token),
            'is_runner': user.is_runner,
            'is_organiser': user.is_organiser,
        }, status=201)
        set_refresh_cookie(response, refresh)
        return response
    return Response(serializer.errors, status=400)


@api_view(['POST'])
def api_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        response = Response({
            'detail': 'Login successful',
            'access': str(refresh.access_token),
            'is_runner': user.is_runner,
            'is_organiser': user.is_organiser,
        }, status=200)
        set_refresh_cookie(response, refresh)
        return response
    return Response({'error': "Invalid credentials"}, status=401)

@api_view(['POST'])
def logout_view(request):
    response = Response({'detail': 'Logged out'})
    response.delete_cookie('refresh_token')
    return response

@ensure_csrf_cookie
@api_view(['GET'])
def get_csrf_token(request):
    return Response({'detail': 'CSRF cookie set'})