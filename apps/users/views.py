# views.py
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from .serializers import RegisterSerializer, UserResponseSerializer


class RegisterView(APIView):
    permission_classes = [AllowAny]  # noqa: RUF012

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Serialize output safely so hashes never leave the server
        output_serializer = UserResponseSerializer(user)
        return Response(output_serializer.data, status=status.HTTP_201_CREATED)
