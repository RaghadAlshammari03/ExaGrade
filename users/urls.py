from django.urls import path
from .views import (
    settings_page, profile_page, signup_view,
    login_view, logout_view, instructor_dashboard, student_dashboard
)

app_name = "users"

urlpatterns = [
    path("settings/", settings_page, name="settings"),
    path("profile/<int:user_id>/", profile_page, name="profile"),
    path("signup/", signup_view, name="signup"),
    path("login/", login_view, name="login"),
    path("logout/", logout_view, name="logout"),
    path("dashboard/instructor/", instructor_dashboard, name="instructor_dashboard"),
    path("dashboard/student/", student_dashboard, name="student_dashboard"),
]
