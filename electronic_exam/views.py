from django.shortcuts import render, get_object_or_404, redirect
from django.views import View
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.contrib import messages
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views.generic import UpdateView
from utils.AI_utils import grade_answer, parse_score_and_feedback
from .models import ElectronicExam, Question, Choice, StudentResponse
from courses.models import Course
from users.models import CustomUser
from utils.AI_utils import grade_answer, parse_score_and_feedback
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json

@method_decorator(login_required, name="dispatch")
class ExamListView(View):
    def get(self, request):
        if request.user.is_instructor:
            exams = ElectronicExam.objects.prefetch_related("questions__responses")
        else:
            enrolled_courses = request.user.enrolled_courses.all()
            exams = ElectronicExam.objects.filter(course__in=enrolled_courses, is_active=True).prefetch_related("questions__responses")

        for exam in exams:
            flagged_responses = [
                response for q in exam.questions.all()
                for response in q.responses.all()
                if response.requires_attention
            ]
            exam.flagged_count = len(flagged_responses)
        return render(request, "electronic_exams/exam_list.html", {"exams": exams})


@method_decorator(login_required, name="dispatch")
class ExamDetailView(View):
    def get(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)

        responses = StudentResponse.objects.filter(
            question__exam=exam,
            student__isnull=False
        ).select_related("student", "question")

        grouped = {}
        for r in responses:
            grouped.setdefault(r.student, []).append(r)

        students_data = []
        for student, responses in grouped.items():
            total_score = sum(r.score or 0 for r in responses)
            students_data.append({
                "student": student,
                "student_id": student.id,
                "score": total_score,
                "max_score": exam.total_marks,
                "score_override": any(r.is_score_override for r in responses),
                "graded_questions": [
                    {
                        "question": r.question.text,
                        "answer": r.answer_text,
                        "score": r.score,
                        "max": r.question.marks,
                        "feedback": r.feedback,
                        "type": r.question.question_type
                    } for r in responses
                ],
                "manual_feedback": responses[0].manual_feedback if responses else "",
                "requires_attention": any(r.requires_attention for r in responses),
                "id": responses[0].id if responses else None,
            })

        graded_count = sum(1 for d in students_data if d["score"] is not None)
        grading_button_text = "Grade Exam" if graded_count == 0 else "Regrade All"

        context = {
            "exam": exam,
            "students_data": students_data,
            "grading_button_text": grading_button_text,
            "grade_chart_data": json.dumps([
                {"name": s["student"].get_full_name(), "score": s["score"]} for s in students_data
            ]),
            "can_send_grades": graded_count > 0,
        }
        context["students_data_json"] = json.dumps(students_data, default=str)
        return render(request, "electronic_exams/exam_detail.html", context)


@method_decorator(login_required, name="dispatch")
class CreateExamView(View):
    def get(self, request, pk=None):
        exam = None
        questions_by_type = {
            "true_false": [],
            "mcq": [],
            "short_answer": [],
            "long_answer": [],
        }

        if pk:
            exam = get_object_or_404(ElectronicExam, pk=pk)
            questions = exam.questions.all()
            for q in questions:
                if q.question_type == "TF":
                    questions_by_type["true_false"].append(q)
                elif q.question_type == "MCQ":
                    q.option_list = [c.text for c in q.choices.all()]
                    questions_by_type["mcq"].append(q)
                elif q.question_type == "SHORT":
                    questions_by_type["short_answer"].append(q)
                elif q.question_type == "LONG":
                    questions_by_type["long_answer"].append(q)

        courses = Course.objects.all()
        return render(request, "electronic_exams/create_exam.html", {
            "courses": courses,
            "exam": exam,
            "questions_by_type": questions_by_type
        })

    def post(self, request, pk=None):
        exam_title = request.POST.get("exam_name")
        course_id = request.POST.get("course")
        total_marks = request.POST.get("total_marks")
        duration = request.POST.get("exam_time")
        can_navigate = request.POST.get("can_navigate") == "true" 

        if not exam_title or not course_id or not total_marks:
            messages.error(request, "Please fill in all required fields!")
            return redirect("electronic_exams:create")

        course = get_object_or_404(Course, id=course_id)

        if pk:
            exam = get_object_or_404(ElectronicExam, pk=pk)
            exam.title = exam_title
            exam.course = course
            exam.total_marks = int(total_marks)
            exam.duration_minutes = int(duration) if duration else None
            exam.can_navigate = can_navigate 
            exam.save()
            exam.questions.all().delete()
        else:
            exam = ElectronicExam.objects.create(
                title=exam_title,
                course=course,
                total_marks=int(total_marks),
                duration_minutes=int(duration) if duration else None,
                can_navigate=can_navigate  
            )

        self._process_questions(request, exam)
        messages.success(request, "Exam saved successfully!")
        return redirect("electronic_exams:exam_list")

    def _process_questions(self, request, exam):
        for question, answer, marks in zip(
            request.POST.getlist("tf_questions[]"),
            request.POST.getlist("tf_answers[]"),
            request.POST.getlist("tf_marks[]")
        ):
            Question.objects.create(
                exam=exam,
                text=question,
                question_type="TF",
                ideal_answer=answer,
                marks=int(marks)
            )

        mcq_questions = request.POST.getlist("mcq_questions[]")
        mcq_answers = request.POST.getlist("mcq_answers[]")
        mcq_options_1 = request.POST.getlist("mcq_options_1[]")
        mcq_options_2 = request.POST.getlist("mcq_options_2[]")
        mcq_options_3 = request.POST.getlist("mcq_options_3[]")
        mcq_options_4 = request.POST.getlist("mcq_options_4[]")
        mcq_marks = request.POST.getlist("mcq_marks[]")

        for i in range(len(mcq_questions)):
            options = [
                mcq_options_1[i],
                mcq_options_2[i],
                mcq_options_3[i],
                mcq_options_4[i],
            ]
            q = Question.objects.create(
                exam=exam,
                text=mcq_questions[i],
                question_type="MCQ",
                ideal_answer=mcq_answers[i],
                marks=int(mcq_marks[i])
            )
            for opt in options:
                Choice.objects.create(
                    question=q,
                    text=opt.strip(),
                    is_correct=(opt.strip() == mcq_answers[i].strip())
                )

        for question, answer, marks in zip(
            request.POST.getlist("short_questions[]"),
            request.POST.getlist("short_correct_answer[]"),
            request.POST.getlist("short_marks[]")
        ):
            Question.objects.create(
                exam=exam,
                text=question,
                question_type="SHORT",
                ideal_answer=answer,
                marks=int(marks)
            )

        for question, answer, marks in zip(
            request.POST.getlist("long_questions[]"),
            request.POST.getlist("long_correct_answer[]"),
            request.POST.getlist("long_marks[]")
        ):
            Question.objects.create(
                exam=exam,
                text=question,
                question_type="LONG",
                ideal_answer=answer,
                marks=int(marks)
            )


@method_decorator(login_required, name="dispatch")
class TakeExamView(View):
    def get(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)

        has_submitted = StudentResponse.objects.filter(student=request.user, question__exam=exam).exists()
        if has_submitted:
            messages.warning(request, "⚠️ You have already submitted this exam.")
            return redirect("electronic_exams:exam_results", pk=exam.pk)

        questions = list(exam.questions.all().order_by("id"))
        
        return render(request, "electronic_exams/take_exam.html", {
            "exam": exam,
            "questions": questions,  
            "can_navigate": exam.can_navigate,
        })


    def post(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)

        if StudentResponse.objects.filter(student=request.user, question__exam=exam).exists():
            messages.error(request, "⚠️ You have already submitted this exam.")
            return redirect("electronic_exams:exam_results", pk=exam.pk)

        questions = list(exam.questions.all().order_by("id"))

        if not exam.can_navigate:
            question_index = int(request.POST.get("question_index", 0))
            if question_index < 0 or question_index >= len(questions):
                messages.error(request, "Invalid question index.")
                return redirect("electronic_exams:take_exam", pk=exam.pk)

            question = questions[question_index]
            answer_text = request.POST.get(f"question_{question.id}", "").strip()
            self._grade_response(request.user, question, answer_text, idx=question_index + 1)

        else:
            for idx, question in enumerate(questions, start=1):
                answer_text = request.POST.get(f"question_{question.id}", "").strip()
                self._grade_response(request.user, question, answer_text, idx=idx)

        exam.update_status()
        messages.success(request, "✅ Exam submitted successfully!")
        return redirect("electronic_exams:exam_results", pk=exam.pk)

    def _grade_response(self, user, question, answer_text, idx):
        correct_answer = question.ideal_answer.strip() if question.ideal_answer else ""
        marks = question.marks or 1
        is_correct = None
        score = 0.0
        feedback = ""
        needs_attention = False

        qtype = question.question_type.upper()

        if qtype in ['SHORT', 'LONG']:
            result = grade_answer(question.text, answer_text, correct_answer, marks)
            score, feedback, needs_attention = parse_score_and_feedback(result, marks, question_number=idx)
        elif qtype in ['TF', 'MCQ']:
            is_correct = answer_text.strip().lower() == correct_answer.strip().lower()
            score = float(marks) if is_correct else 0.0
            feedback = f"Question {idx}: {'Correct ✅' if is_correct else 'Incorrect ❌'}"
            needs_attention = False
        else:
            feedback = f"Unsupported question type: {qtype}"

        StudentResponse.objects.create(
            student=user,
            exam=question.exam,
            question=question,
            answer_text=answer_text,
            is_correct=is_correct,
            score=score,
            feedback=feedback,
            requires_attention=needs_attention
        )

@method_decorator(login_required, name="dispatch")
class EditExamView(UpdateView):
    model = ElectronicExam
    fields = ["title", "total_marks", "course"]
    template_name = "electronic_exams/edit_exam.html"
    success_url = reverse_lazy("electronic_exams:exam_list")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["courses"] = Course.objects.all()
        return context


@method_decorator(login_required, name="dispatch")
class DeleteQuestionView(View):
    def post(self, request, question_id):
        get_object_or_404(Question, id=question_id).delete()
        return JsonResponse({"message": "Question deleted successfully!"})


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


class DeleteExamView(View):
    def post(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        exam.delete()
        messages.success(request, "Exam deleted successfully!")
        return redirect('electronic_exams:exam_list')

@require_POST
@login_required
def regrade_response(request, response_id):
    response = get_object_or_404(StudentResponse, id=response_id)
    question = response.question
    exam = response.question.exam
    result = grade_answer(question.text, response.answer_text, question.ideal_answer, question.marks)
    score, feedback, needs_attention = parse_score_and_feedback(result, question.marks)

    response.score = score
    response.feedback = feedback
    response.requires_attention = needs_attention
    response.save()

    
    exam.update_status()
    return JsonResponse({"success": True})

@require_POST
@login_required
def toggle_flag_review(request, response_id):
    response = get_object_or_404(StudentResponse, id=response_id)
    response.flagged_for_review = not response.flagged_for_review
    response.save()
    return JsonResponse({"success": True})

def grade_student_response(response):
    print("⚠️ Grading response for:", response.student)
    print("Answer Text:", response.answer_text)
    print("Question Type:", response.question.question_type)

    if not response.answer_text:
        print("❌ No answer text. Skipping grading.")
        return  # Early exit
    
    question = response.question
    eval_type = question.eval_type
    custom_note = question.custom_eval or ""

    # ✨ Add this logic to handle MCQ / TF properly
    if question.question_type in ["TF", "MCQ"]:
        is_correct = response.answer_text.strip().lower() == question.ideal_answer.strip().lower()
        response.score = question.marks if is_correct else 0
        response.feedback = f"Question: {question.text}\nAnswer: {response.answer_text}\nFeedback: {'Correct ✅' if is_correct else 'Incorrect ❌'}"
        response.requires_attention = False
    else:
        result = grade_answer(
            question=question.text,
            student_text=response.answer_text,
            solution_text=question.ideal_answer,
            marks=question.marks,
            eval_type=eval_type,
            custom_note=custom_note,
            question_type=question.question_type.lower()
        )
        score, feedback, needs_attention = parse_score_and_feedback(result, question.marks)
        response.score = score
        response.feedback = feedback
        response.requires_attention = needs_attention

    response.save()

@require_POST
@login_required
def grade_exam_view(request, exam_id):
    exam = get_object_or_404(ElectronicExam, pk=exam_id)
    mode = request.POST.get("mode", "").lower() 
    responses = StudentResponse.objects.filter(question__exam=exam)

    for r in responses:
        if mode == "new" and not r.requires_attention:
            continue
        elif mode == "regrade":
            r.score = 0
            r.feedback = ""
            r.requires_attention = False
        grade_student_response(r)

    exam.update_status()
    return JsonResponse({
        "success": True,
        "new_status": exam.get_status_display(),
        "status_key": exam.status,
    })

@require_POST
@login_required
def grade_individual_response(request, exam_id, response_id):
    exam = get_object_or_404(ElectronicExam, id=exam_id)
    response = get_object_or_404(StudentResponse, id=response_id, question__exam=exam)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    grade_student_response(response)
    exam.update_status()

    return JsonResponse({
        "success": True,
        "student": response.student.get_full_name(),
        "score": response.score,
        "feedback": response.feedback
    })

@require_POST
@login_required
@csrf_exempt
def resolve_response_flag(request, response_id):
    response = get_object_or_404(StudentResponse, id=response_id)
    if request.user != response.question.exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
    try:
        manual_score = float(request.POST.get("manual_score"))
        if manual_score > response.question.marks:
            return JsonResponse({"success": False, "error": "Score exceeds max marks."})
        response.score = manual_score
        response.requires_attention = False
        response.save()
        response.question.exam.update_status()
        return JsonResponse({"success": True})
    except:
        return JsonResponse({"success": False, "error": "Invalid input."})

@require_POST
@login_required
def send_grades_electronic(request, exam_id):
    exam = get_object_or_404(ElectronicExam, id=exam_id)

    if not request.user.is_instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    # Mark grades as released
    exam.grades_released = True
    exam.was_done_once = True
    exam.save()

    send_options = request.POST.getlist("send_options")  

    students = CustomUser.objects.filter(
        enrolled_courses=exam.course,
        responses__question__exam=exam
    ).distinct()

    for student in students:
        responses = StudentResponse.objects.filter(student=student, question__exam=exam)

        score = sum(r.score or 0 for r in responses)
        feedback_parts = []
        manual_feedback_parts = []

        for r in responses:
            if "ai-feedback" in send_options and r.feedback:
                feedback_parts.append(
                    f"Q: {r.question.text}\nAnswer: {r.answer_text}\nScore: {r.score}/{r.question.marks}\nFeedback: {r.feedback}"
                )
            if "instructor-feedback" in send_options and r.manual_feedback:
                manual_feedback_parts.append(r.manual_feedback)

        message = []

        if "grade" in send_options:
            message.append(f"Score: {score} / {exam.total_marks}")

        if feedback_parts:
            message.append("AI Feedback:\n" + "\n".join(feedback_parts))

        if manual_feedback_parts:
            message.append("Instructor Feedback:\n" + "\n".join(manual_feedback_parts))

    messages.success(request, "✅ Grades sent successfully!")
    return redirect("electronic_exams:exam_detail", pk=exam_id)


@require_POST
@login_required
def save_feedback(request, response_id):
    feedback = request.POST.get("feedback", "")
    response = get_object_or_404(StudentResponse, id=response_id)

    if not request.user.is_instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    response.manual_feedback = feedback
    response.save()
    return JsonResponse({"success": True})

@require_POST
@login_required
def ajax_save_answer(request):
    exam_id = request.POST.get("exam_id")
    exam = get_object_or_404(ElectronicExam, id=exam_id)

    for key, value in request.POST.items():
        if key.startswith("question_"):
            qid = key.split("_")[1]
            question = get_object_or_404(Question, id=qid, exam=exam)
            StudentResponse.objects.update_or_create(
                student=request.user,
                question=question,
                exam=exam,
                defaults={"answer_text": value}
            )
    return JsonResponse({"success": True})


@method_decorator(login_required, name="dispatch")
class Exam_results_view(View):
    def get(self, request, pk):
        exam = get_object_or_404(ElectronicExam, pk=pk)
        student_responses = StudentResponse.objects.filter(student=request.user, question__exam=exam)

        if not student_responses.exists():
            return redirect("courses:detail", course_id=exam.course.id)

        if exam.grades_released:
            total_score = sum(r.score or 0 for r in student_responses)
            total_marks = sum(r.question.marks for r in student_responses)
            ai_feedback = "\n\n".join([r.feedback or "" for r in student_responses])
        else:
            total_score = None
            total_marks = None
            ai_feedback = None

        instructor_feedback = student_responses.first().manual_feedback if student_responses.first() else ""

        return render(request, "electronic_exams/exam_detail_student.html", {
            "exam": exam,
            "responses": student_responses,
            "student_score": total_score,
            "total_marks": total_marks,
            "ai_feedback": ai_feedback,
            "instructor_feedback": instructor_feedback,
        })

@require_POST
@login_required
def override_score(request, response_id):
    response = get_object_or_404(StudentResponse, id=response_id)

    if request.user != response.question.exam.course.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    try:
        new_score = float(request.POST.get("score", 0))
        max_score = response.question.marks 
        if new_score < 0 or new_score > max_score:
            return JsonResponse({"success": False, "error": "Score exceeds max marks."})
        response.score = new_score
        response.is_score_override = True
        response.save()
        response.question.exam.update_status()
        return JsonResponse({"success": True})
    except Exception as e:
        return JsonResponse({"success": False, "error": str(e)})
