from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate, login
from .models import CustomUser
from .serializers import UserSerializer

@api_view(['POST'])
def api_register(request):
    serializer = UserSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'detail': 'User registered successfully',
            'access': str(refresh.access_token),
            'is_runner': user.is_runner,
            'is_organiser': user.is_organiser,
        }, status=200)
    return Response(serializer.errors, status=400)

@api_view(['POST'])
def api_login(request):
    username = request.data.get('username')
    password = request.data.get('password')
    user = authenticate(username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            'detail': 'Login successful',
            'access': str(refresh.token),
            'is_runner': user.is_runner,
            'is_organiser': user.is_orgaiser,
        }, status=200)
    return Response({'error': "Invalid credentials"}, status=401)