from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from users.views import home_view

urlpatterns = [
    path("", home_view, name="home"),  # ✅ Home page
    path("admin/", admin.site.urls),  # ✅ Admin panel
    path("users/", include("users.urls", namespace="users")),  # ✅ User management
    path("courses/", include("courses.urls", namespace="courses")),  # ✅ Courses
    path("exams/", include("exams.urls", namespace="exams")),  # ✅ Exams
    path("electronic_exams/", include("electronic_exams.urls")),
]

# ✅ Ensure media files (PDFs, images) work in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
