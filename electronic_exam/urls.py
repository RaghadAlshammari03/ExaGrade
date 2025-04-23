from django.urls import path
from . import views
from .views import send_grades_electronic

app_name = "electronic_exams"

urlpatterns = [
    path("", views.ExamListView.as_view(), name="exam_list"),
    path("create/", views.CreateExamView.as_view(), name="create"),
    path("create/<int:pk>/", views.CreateExamView.as_view(), name="edit_exam"),
    path("<int:pk>/", views.ExamDetailView.as_view(), name="exam_detail"),
    path("<int:pk>/take/", views.TakeExamView.as_view(), name="take_exam"),
    path("question/<int:question_id>/delete/", views.DeleteQuestionView.as_view(), name="delete_question"),
    path("<int:pk>/toggle/", views.ToggleExamView.as_view(), name="toggle_exam"),
    path("question/<int:pk>/update/", views.UpdateQuestionView.as_view(), name="update_question"),
    path("<int:pk>/delete/", views.DeleteExamView.as_view(), name="delete_exam"),
    path("regrade/<int:response_id>/", views.regrade_response, name="regrade_response"),
    path("toggle-flag/<int:response_id>/", views.toggle_flag_review, name="toggle_flag"),
    path('grade-exam/<int:exam_id>/', views.grade_exam_view, name='grade_exam'),
    path("save-feedback/<int:response_id>/", views.save_feedback, name="save_feedback"),
    path('send-grades/<int:exam_id>/', send_grades_electronic, name="send_grades"),
    path("ajax-save-answer/", views.ajax_save_answer, name="ajax_save_answer"),
    path("<int:pk>/results/", views.Exam_results_view.as_view(), name="exam_results"),
    path("<int:exam_id>/grade-one/<int:response_id>/", views.grade_individual_response, name="grade_one_student"),
    path("override-score/<int:response_id>/", views.override_score, name="override_score"),
]
