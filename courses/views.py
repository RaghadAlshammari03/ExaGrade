from django.shortcuts import render, get_object_or_404, redirect
from .models import Course
from exams.models import Exam, Grade
from .forms import CourseForm
from django.utils.crypto import get_random_string
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from users.models import CustomUser
from django.views.decorators.http import require_POST
from electronic_exam.models import ElectronicExam
from electronic_exam.models import ElectronicExam, StudentResponse

@login_required
def course_list(request):
    if request.user.is_instructor:
        courses = Course.objects.filter(instructor=request.user)
    else:
        courses = request.user.enrolled_courses.all()

    if request.method == "POST" and request.user.is_instructor:
        name = request.POST.get("name")
        description = request.POST.get("description")
        course_code = get_random_string(6).upper()
        Course.objects.create(
            name=name,
            description=description,
            instructor=request.user,
            course_code=course_code
        )
        return redirect("courses:list")

    enroll_error = request.session.pop("enroll_error", None)
    typed_code = request.session.pop("typed_code", "")
    enrolled_success = request.session.pop("enrolled_success", False)

    return render(request, "courses/course_list.html", {
        "courses": courses,
        "enroll_error": enroll_error,
        "typed_code": typed_code,
        "enrolled_success": enrolled_success,
    })

@login_required
def enroll_course(request):
    if request.method == "POST":
        course_code = request.POST.get("course_code")
        try:
            course = Course.objects.get(course_code=course_code)
            request.user.enrolled_courses.add(course)
            request.session["enrolled_success"] = True  
            return redirect("courses:list")
        except Course.DoesNotExist:
            request.session["enroll_error"] = "❌ Invalid course code. Please check and try again."
            request.session["typed_code"] = course_code
            return redirect("courses:list")

@login_required
def course_detail_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    paper_exams = Exam.objects.filter(course=course)
    electronic_exams = ElectronicExam.objects.filter(course=course)
    students = course.students.all() if request.user.is_instructor else None
    grades = None

    all_exams = []

    if request.user.is_student:
        # ✅ Only include paper exams if student has a grade
        for exam in paper_exams:
            exam.exam_type = "paper"
            grade = Grade.objects.filter(exam=exam, student=request.user).first()
            if grade:
                final_score = grade.manual_override if grade.manual_override is not None else grade.grade
                exam.student_grade = {
                    "score": final_score,
                    "feedback": grade.feedback
                }
                all_exams.append(exam)  # ✅ Append only if grade exists

        # ✅ Handle electronic exams (submitted or active only)
        for exam in electronic_exams:
            exam.exam_type = "electronic"
            responses = StudentResponse.objects.filter(student=request.user, question__exam=exam)
            exam.is_submitted_by_user = responses.exists()

            if exam.is_submitted_by_user or exam.is_active:
                if exam.grades_released and exam.is_submitted_by_user:
                    exam.student_score = sum(r.score or 0 for r in responses)
                    exam.total_score = sum(r.question.marks for r in responses)
                    exam.student_feedback = "\n".join([r.feedback or "" for r in responses])
                else:
                    exam.student_score = None
                    exam.total_score = None
                    exam.student_feedback = None

                all_exams.append(exam)

    else:
        # ✅ Instructor view — include all exams
        all_exams = list(paper_exams) + list(electronic_exams)
        for exam in all_exams:
            exam.exam_type = "paper" if isinstance(exam, Exam) else "electronic"

        grades = Grade.objects.filter(exam__in=paper_exams)

    return render(request, "courses/course_detail.html", {
        "course": course,
        "exams": all_exams,
        "grades": grades,
        "students": students,
    })


@login_required
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    if request.user != course.instructor:
        messages.error(request, "You are not authorized to delete this course.")
        return redirect("courses:detail", course_id=course.id)

    course.delete()
    messages.success(request, "Course deleted successfully.")
    
    return redirect("courses:list")

@login_required
def add_course(request):
    if request.method == "POST":
        form = CourseForm(request.POST)
        if form.is_valid():
            course = form.save(commit=False)
            course.instructor = request.user  
            course.save()
            messages.success(request, "✅ Course added successfully!")
            return redirect("courses:list")  
        else:
            messages.error(request, "⚠️ Please fill in all required fields.")
    else:
        form = CourseForm()
    return render(request, "courses/add_course.html", {"form": form})

@login_required
def student_grades_view(request, student_id):
    student = get_object_or_404(CustomUser, id=student_id)

    if request.user != student and not request.user.is_instructor:
        messages.error(request, "⚠️ You do not have permission to view these grades.")
        return redirect("courses:list")

    grades = Grade.objects.filter(student=student).select_related("exam")

    return render(request, "courses/student_grades.html", {
        "student": student,
        "grades": grades
    })

@login_required
@require_POST
def edit_course_name(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Only instructor can update
    if request.user != course.instructor:
        messages.error(request, "You are not authorized to edit this course.")
        return redirect("courses:detail", course_id=course.id)

    new_name = request.POST.get("new_name", "").strip()

    if new_name:
        course.name = new_name
        course.save()
        messages.success(request, "✅ Course name updated successfully.")
    else:
        messages.error(request, "⚠️ Course name cannot be empty.")

    return redirect("courses:detail", course_id=course.id)