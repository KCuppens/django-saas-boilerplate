from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import FileUploadViewSet, file_download_view

router = DefaultRouter()
router.register(r"files", FileUploadViewSet, basename="file")

urlpatterns = [
    path("", include(router.urls)),
    # Direct file download (fallback)
    path("files/download/<uuid:file_id>/", file_download_view, name="file_download"),
]
