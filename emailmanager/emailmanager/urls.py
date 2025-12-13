"""
URL configuration for emailmanager project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path
from core import views

urlpatterns = [
    path("admin/", admin.site.urls),

        # UI pages
    path('', views.home_page),
    # path('list-unread/', views.list_unread_page),

    # API endpoints (DRF)
    path("api/test-auth/", views.test_auth),
    path("api/list-recent-unread/", views.list_recent_unread),
    path("api/list-oldest-unread/", views.list_oldest_unread),
    path("api/delete-old/", views.delete_old),

    path('api/delete-message/<str:message_id>/', views.delete_single_email, name='delete_single'),

    path('api/batch-delete/', views.batch_delete_emails, name='batch_delete'),

]
