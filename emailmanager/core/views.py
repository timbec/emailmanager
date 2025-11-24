from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from .gmail_auth import authenticate_gmail
from .serializers import DeleteOldEmailsSerializer
from .services import (
    test_authentication,
    list_recent_unread_emails,
    delete_old_unread_emails,
    list_oldest_unread_emails,
)


def home_page(request):
    return render(request, "core/home.html")


def list_unread_page(request):
    service = authenticate_gmail()
    emails = list_recent_unread_emails(service, days=30)
    return render(request, "core/list_unread.html", {"emails": emails})


@api_view(["GET"])
def test_auth(request):
    if test_authentication():
        return Response({"message": "Authentication successful!"})
    return Response(
        {"message": "Authentication failed, please check your credentials."},
        status=status.HTTP_400_BAD_REQUEST,
    )

@api_view(["GET"])
def list_oldest_unread(request):
    service = authenticate_gmail()
    emails = list_oldest_unread_emails(service, limit=50)
    return Response({"emails": emails})


@api_view(["GET"])
def list_recent_unread(request):
    service = authenticate_gmail()
    emails = list_recent_unread_emails(service, days=30)
    return Response({"emails": emails})


@api_view(["POST"])
def delete_old(request):
    serializer = DeleteOldEmailsSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    days_old = serializer.validated_data["days_old"]

    service = authenticate_gmail()
    # For now we ignore days_old in the service; we’ll wire it up shortly
    deleted_count = delete_old_unread_emails(service)

    return Response({"deleted_count": deleted_count})

