from django.urls import path
from .views import (
    exam_list_view,
    exam_detail_view,
    add_exam,
    add_question,
    edit_question,
    exam_students_grades,
    download_pdf,
    upload_pdf  # ✅ Ensure this is correctly imported
)

app_name = "exams"

urlpatterns = [
    path("", exam_list_view, name="list"),
    path("<int:exam_id>/", exam_detail_view, name="detail"),
    path("add/", add_exam, name="add"),
    path("<int:exam_id>/add-question/", add_question, name="add_question"),
    path("question/<int:question_id>/edit/", edit_question, name="edit_question"),
    path("<int:exam_id>/grades/", exam_students_grades, name="students_grades"),
    path("<int:exam_id>/download-pdf/", download_pdf, name="download_pdf"),
    path("<int:exam_id>/upload-pdf/", upload_pdf, name="upload_pdf"),  # ✅ Ensure this exists
]
