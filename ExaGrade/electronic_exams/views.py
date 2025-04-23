from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.urls import reverse_lazy
from django.views.generic import UpdateView  # ✅ Ensure this is imported


# ✅ Import models properly
from .models import ElectronicExam, Question, Choice, StudentResponse
from courses.models import Course
from users.models import CustomUser

# ✅ Check if 'UpdateQuestionView' is missing, remove its import from urls.py

# ✅ Exam List View
@method_decorator(login_required, name="dispatch")
class ExamListView(View):
    def get(self, request):
        exams = ElectronicExam.objects.all()
        return render(request, "electronic_exams/exam_list.html", {"exams": exams})


# ✅ Exam Detail View
@method_decorator(login_required, name="dispatch")
class ExamDetailView(View):
    def get(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        questions = exam.questions.all()
        students = CustomUser.objects.filter(responses__question__exam=exam).distinct()
        return render(
            request, 
            "electronic_exams/exam_detail.html", 
            {"exam": exam, "questions": questions, "students": students}
        )


# ✅ Create Exam View
@method_decorator(login_required, name="dispatch")
class CreateExamView(View):
    def get(self, request):
        courses = Course.objects.all()
        return render(request, "electronic_exams/create_exam.html", {"courses": courses})

    def post(self, request):
        exam_title = request.POST.get("exam_name")
        course_id = request.POST.get("course")
        total_marks = request.POST.get("total_marks")
        duration = request.POST.get("exam_time")
        
        if not exam_title or not course_id or not total_marks:
            messages.error(request, "Please fill in all required fields!")
            return redirect("electronic_exams:create_exam")

        course = get_object_or_404(Course, id=course_id)
        exam = ElectronicExam.objects.create(
            title=exam_title,
            course=course,
            total_marks=int(total_marks),
            duration_minutes=int(duration) if duration else None
        )
        
        # ✅ Process and Save Questions
        self._process_questions(request, exam)

        messages.success(request, "Exam created successfully!")
        return redirect("electronic_exams:exam_list")
    
    def _process_questions(self, request, exam):
        # ✅ True/False Questions
        for question, answer in zip(request.POST.getlist("tf_questions[]"), request.POST.getlist("tf_answers[]")):
            Question.objects.create(exam=exam, text=question, question_type="TF", ideal_answer=answer)
        
        # ✅ Multiple Choice Questions
        for question, options, answer in zip(request.POST.getlist("mcq_questions[]"), request.POST.getlist("mcq_options[]"), request.POST.getlist("mcq_answers[]")):
            q = Question.objects.create(exam=exam, text=question, question_type="MCQ", ideal_answer=answer)
            for option in options.split(","):
                Choice.objects.create(question=q, text=option.strip(), is_correct=option.strip() == answer.strip())
        
        # ✅ Short and Long Answer Questions
        for question, answer in zip(request.POST.getlist("short_questions[]"), request.POST.getlist("short_model_answers[]")):
            Question.objects.create(exam=exam, text=question, question_type="SHORT", ideal_answer=answer)
        
        for question, answer in zip(request.POST.getlist("long_questions[]"), request.POST.getlist("long_model_answers[]")):
            Question.objects.create(exam=exam, text=question, question_type="LONG", ideal_answer=answer)


# ✅ Take Exam View
@method_decorator(login_required, name="dispatch")
class TakeExamView(View):
    def get(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        return render(request, "electronic_exams/take_exam.html", {"exam": exam, "questions": exam.questions.all()})

    def post(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        student = request.user  
        
        for question in exam.questions.all():
            answer_text = request.POST.get(f"question_{question.id}", "").strip()
            correct_answer = question.ideal_answer.strip() if question.ideal_answer else None
            is_correct = (answer_text.lower() == correct_answer.lower()) if correct_answer else None
            score = 1.0 if is_correct else 0.0

            StudentResponse.objects.create(
                student=student, question=question, answer_text=answer_text, is_correct=is_correct, score=score
            )

        messages.success(request, "Exam submitted successfully!")
        return redirect("electronic_exams:exam_results", pk=exam.pk)


# ✅ Exam Results View
@method_decorator(login_required, name="dispatch")
class ExamResultsView(View):
    def get(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        student_responses = StudentResponse.objects.filter(student=request.user, question__exam=exam)
        return render(request, "electronic_exams/exam_results.html", {"exam": exam, "responses": student_responses})


# ✅ Edit Exam View (Fixed Course Issue)
@method_decorator(login_required, name="dispatch")
class EditExamView(UpdateView):
    model = ElectronicExam
    fields = ["title", "total_marks", "course"]
    template_name = "electronic_exams/edit_exam.html"
    success_url = reverse_lazy("electronic_exams:exam_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["courses"] = Course.objects.all()  # ✅ Ensure courses are available in the template
        return context

# ✅ Delete Question View
@method_decorator(login_required, name="dispatch")
class DeleteQuestionView(View):
    def post(self, request, question_id):
        get_object_or_404(Question, id=question_id).delete()
        return JsonResponse({"message": "Question deleted successfully!"})


# ✅ Toggle Exam Activation
@method_decorator(login_required, name="dispatch")
class ToggleExamView(View):
    def post(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        exam.is_active = not exam.is_active
        exam.save()
        return JsonResponse({"status": "success", "is_active": exam.is_active})
    

@method_decorator(login_required, name="dispatch")
class UpdateQuestionView(UpdateView):
    model = Question
    fields = ["text", "question_type", "ideal_answer"]
    template_name = "electronic_exams/update_question.html"
    
    def get_success_url(self):
        return reverse_lazy("electronic_exams:exam_detail", kwargs={"pk": self.object.exam.pk})