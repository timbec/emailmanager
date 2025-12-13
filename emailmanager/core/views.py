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

@api_view(["GET"])
def test_auth(request):
    if test_authentication():
        return Response({"message": "Authentication successful!"})
    return Response(
        {"message": "Authentication failed, please check your credentials."},
        status=status.HTTP_400_BAD_REQUEST,
    )


def home_page(request):
    return render(request, "core/home.html")


def list_unread_page(request):
    service = authenticate_gmail()
    emails = list_recent_unread_emails(service, days=30)
    return render(request, "core/list_unread.html", {"emails": emails})


@api_view(["GET"])
def list_oldest_unread(request):
    service = authenticate_gmail()
    emails = list_oldest_unread_emails(service, limit=50, days = 5110)
    print(emails)
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

@api_view(["DELETE"])
def delete_single_email(request, message_id):
    """
    Deletes a single email by ID.
    """
    try:
        service = authenticate_gmail()
        service.users().messages().delete(
            userId="me",
            id=message_id
        ).execute()
        
        return Response({"status": "success", "message_id": message_id})
    except Exception as e:
        return Response({"error": str(e)}, status=500)


def review_page(request):
    return render(request, 'review.html')


@api_view(["POST"])
def batch_delete_emails(request):
    """
    Receives a list of IDs: {'ids': ['123', '456', ...]}
    Deletes them all instantly using Gmail's batchDelete.
    """
    ids_to_delete = request.data.get("ids", [])
    
    if not ids_to_delete:
        return Response({"error": "No IDs provided"}, status=400)

    try:
        service = authenticate_gmail()
        
        # This is the "magic" method that deletes multiple emails in one go
        service.users().messages().batchDelete(
            userId="me",
            body={"ids": ids_to_delete}
        ).execute()
        
        return Response({
            "status": "success", 
            "deleted_count": len(ids_to_delete)
        })
        
    except Exception as e:
        return Response({"error": str(e)}, status=500)
