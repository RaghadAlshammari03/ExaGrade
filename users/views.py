from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from users.models import CustomUser
from courses.models import Course
from .forms import UserProfileForm, SignupForm, LoginForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from exams.models import Exam
from django.contrib import messages
from django.utils.dateformat import format as date_format
import json
from django.core.serializers.json import DjangoJSONEncoder
from electronic_exam.models import ElectronicExam

def home_view(request):
    """ Redirects logged-in users to their dashboard instead of the home page """
    if request.user.is_authenticated:
        if request.user.is_instructor:
            return redirect(reverse("users:instructor_dashboard"))
        else:
            return redirect(reverse("users:student_dashboard"))
    
    return render(request, "users/home.html")

@login_required
def settings_page(request):
    if request.method == "POST":
        form = UserProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Profile updated successfully!")
            return redirect(reverse("users:profile", kwargs={"user_id": request.user.id})) 
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, "users/settings.html", {"form": form})

@login_required
def profile_page(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    return render(request, "users/profile.html", {"profile_user": user})

def signup_view(request):
    if request.method == "POST":
        form = SignupForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)

            messages.success(request, "🎉 Signup successful! Welcome to ExaGrade.")

            if user.is_instructor:
                return redirect("users:instructor_dashboard")
            else:
                return redirect("users:student_dashboard")
        else:
            messages.error(request, "⚠️ Signup failed. Please fix the errors below.")
    
    else:
        form = SignupForm()

    return render(request, "users/signup.html", {"form": form})


def login_view(request):
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)

            messages.success(request, f"Welcome back, {user.username}!")

            if user.is_instructor:
                return redirect("users:instructor_dashboard")
            else:
                return redirect("users:student_dashboard")
        else:
            messages.error(request, "⚠️ Invalid username or password. Please try again.")

    else:
        form = LoginForm()

    return render(request, "users/login.html", {"form": form})

def logout_view(request):
    logout(request)
    messages.info(request, "👋 You've been logged out.")
    return redirect("home")

@login_required
def instructor_dashboard(request):
    if not request.user.is_instructor:
        return redirect("users:student_dashboard")

    courses = Course.objects.filter(instructor=request.user)
    paper_exams = Exam.objects.filter(course__in=courses)
    electronic_exams = ElectronicExam.objects.filter(course__in=courses)

    combined_exams = list(paper_exams) + list(electronic_exams)

    exam_data = [
        {
            "title": exam.name if hasattr(exam, 'name') else exam.title,
            "start": exam.created_at.strftime('%Y-%m-%d'),
            "url": f"/exams/{exam.id}/" if hasattr(exam, 'grades') else f"/electronic-exams/{exam.id}/",
            "color": "#3b82f6"
        }
        for exam in combined_exams
    ]

    exam_names = []
    average_scores = []
    all_exam_data = []

    for exam in combined_exams:
        is_paper = hasattr(exam, 'grades')
        grades = exam.grades.all() if is_paper else exam.student_responses.all()
        if grades.exists():
            avg = sum(float(g.grade if is_paper else g.score) for g in grades if (g.grade if is_paper else g.score) not in [None, ""]) / grades.count()
            name = exam.name if is_paper else exam.title
            all_exam_data.append({
                "name": name,
                "score": round(avg, 2),
                "date": exam.created_at.strftime('%Y-%m-%d'),
                "course": exam.course.name
            })
            exam_names.append(name)
            average_scores.append(round(avg, 2))

    return render(request, "users/instructor_dashboard.html", {
        "courses": courses,
        "exams": combined_exams,  
        "exam_data": exam_data,
        "exam_names": json.dumps(exam_names),
        "average_scores": json.dumps(average_scores),
        "all_exam_data": json.dumps(all_exam_data, cls=DjangoJSONEncoder),
    })


@login_required
def student_dashboard(request):
    if request.user.is_instructor:
        return redirect("users:instructor_dashboard")

    enrolled_courses = request.user.enrolled_courses.all()
    grades = request.user.grades_received.select_related("exam").all()

    grades_with_final = [
        {
            "exam": g.exam,
            "score": g.final_score(),
            "exam_id": g.exam.id,
            "exam_name": g.exam.name,
            "course_name": g.exam.course.name,
            "date": g.exam.created_at,
            "grade": g  
        }
        for g in grades
        if g.final_score() not in [None, ""]
    ]

    return render(request, "users/student_dashboard.html", {
        "enrolled_courses": enrolled_courses,
        "grades": grades_with_final
    })
