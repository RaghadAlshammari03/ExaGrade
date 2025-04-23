from django.urls import path
from . import views

from .views import add_course, course_detail_view, course_list, delete_course, enroll_course

app_name = "courses"

urlpatterns = [
    path("", course_list, name="list"),
    path('<int:course_id>/', course_detail_view, name="detail"),
    path("<int:course_id>/delete/", delete_course, name="delete"), 
    path("add/", add_course, name="add"),
    path('enroll/', enroll_course, name="enroll"), 
    path("<int:course_id>/edit-name/", views.edit_course_name, name="edit_course_name"),
    path("student/<int:student_id>/grades/", views.student_grades_view, name="student_grades"),
]
