from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from users.models import CustomUser
from courses.models import Course
from .forms import UserProfileForm, SignupForm, LoginForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from exams.models import Exam
from django.contrib import messages

def home_view(request):
    """ Redirects logged-in users to their dashboard instead of the home page """
    if request.user.is_authenticated:
        if request.user.is_instructor:
            return redirect(reverse("users:instructor_dashboard"))
        else:
            return redirect(reverse("users:student_dashboard"))
    
    return render(request, "users/home.html")  # Show home only if user is not logged in

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
    messages.info(request, "👋 You've been logged out. See you soon!")
    return redirect("users:login")

@login_required
def instructor_dashboard(request):
    if not request.user.is_instructor:
        return redirect("users:student_dashboard")

    courses = Course.objects.filter(instructor=request.user)
    exams = Exam.objects.filter(course__in=courses)

    return render(request, "users/instructor_dashboard.html", {"courses": courses, "exams": exams})


@login_required
def student_dashboard(request):
    if request.user.is_instructor:
        return redirect("users:instructor_dashboard")

    enrolled_courses = request.user.enrolled_courses.all()
    grades = request.user.grades_received.all()

    return render(request, "users/student_dashboard.html", {"enrolled_courses": enrolled_courses, "grades": grades})


