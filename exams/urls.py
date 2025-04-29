from django.urls import path
from . import views

app_name = "exams"

urlpatterns = [
    path("", views.exam_list_view, name="list"),
    path("add/", views.add_or_edit_exam, name="add"),
    path("<int:exam_id>/", views.exam_detail_view, name="detail"), 
    path("<int:exam_id>/edit/", views.edit_exam, name="edit_exam"),
    path("<int:exam_id>/delete/", views.delete_exam, name="delete_exam"),
    path("<int:exam_id>/grade/", views.grade_exam, name="grade_exam"),
    path("<int:exam_id>/grades/", views.exam_students_grades, name="exam_students_grades"),
    path("<int:exam_id>/generate-paper/", views.generate_exam_pdf, name="generate_exam_pdf"),
    path('answered-pdf/<int:exam_id>/', views.generate_answered_pdf, name='generate_answered_pdf'),
    path("<int:exam_id>/upload-student-paper/", views.upload_student_paper, name="upload_student_paper"),
    path("paper/delete/<int:paper_id>/", views.delete_paper, name="delete_paper"),
    path("<int:exam_id>/send-grades/", views.send_grades, name="send_grades"),
    path('calendar/events/', views.calendar_events, name='calendar_events'),
    path('<int:exam_id>/override/<int:paper_id>/', views.override_score, name='override_score'),
    path('<int:paper_id>/edit-name/', views.edit_student_name, name='edit_student_name'),
    path('<int:paper_id>/edit-id/', views.edit_student_id, name='edit_student_id'),
    path('save-feedback/<int:paper_id>/', views.save_instructor_feedback, name='save_feedback'),
    path('<int:exam_id>/grade/student/<int:paper_id>/', views.grade_individual_student, name='grade_one_student'),
    path('<int:exam_id>/merge/', views.merge_papers_by_id, name='merge_papers_by_id'),
    path("merge/<int:exam_id>/", views.merge_papers, name="merge_papers"),
    path('<int:exam_id>/unmerge/', views.unmerge_papers, name='unmerge_papers'),
    path('<int:exam_id>/unmerge-by-id/', views.unmerge_papers_by_id, name='unmerge_papers_by_id'),
    path('<int:exam_id>/merge/resolve-name/', views.resolve_name_conflict_merge, name='resolve_name_conflict_merge'),
    path('<int:exam_id>/grade/student/<int:paper_id>/', views.grade_individual_student, name='grade_one_student'),
    path('exam/<int:exam_id>/delete-all-papers/', views.delete_all_papers, name='delete_all_papers'),
    path("resolve-flag/<int:issue_id>/", views.resolve_flag, name="resolve_flag"),
    path('preview-exam-pdf/', views.preview_exam_pdf, name='preview_exam_pdf'),
    path('preview-answered-pdf/', views.preview_answered_pdf, name='preview_answered_pdf'),
]