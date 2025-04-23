from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.contrib import messages
from django.apps import apps
from django.core.files.storage import default_storage
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.lib.utils import simpleSplit

from .models import Exam, Question
from .forms import ExamForm, QuestionForm
from courses.models import Course

import logging
logger = logging.getLogger(__name__)

# ✅ Load Grade model dynamically to avoid circular import issues
Grade = apps.get_model("exams", "Grade")


@login_required
def exam_list_view(request):
    """View to list all exams for a course."""
    if request.user.is_instructor:
        exams = Exam.objects.filter(course__in=request.user.courses.all())
    else:
        exams = Exam.objects.filter(course__in=request.user.enrolled_courses.all())

    return render(request, "exams/exam_list.html", {"exams": exams})


@login_required
def exam_detail_view(request, exam_id):
    """View to show details of a specific exam."""
    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()

    logger.debug(f"Rendering exam {exam.id} - {exam.name}")

    return render(request, "exams/exam_detail.html", {
        "exam": exam,
        "questions": questions
    })


@login_required
def add_exam(request):
    """View to add a new exam."""
    if not request.user.is_instructor:
        return redirect("exams:list")

    if request.method == "POST":
        form = ExamForm(request.POST)
        course_id = request.POST.get("course_id")

        course = get_object_or_404(Course, id=course_id, instructor=request.user)

        if form.is_valid():
            exam = form.save(commit=False)
            exam.course = course
            exam.instructor = request.user
            exam.save()
            messages.success(request, "✅ Exam created successfully!")
            return redirect("courses:detail", course_id=course.id)

    else:
        form = ExamForm()

    courses = Course.objects.filter(instructor=request.user)
    return render(request, "exams/add_exam.html", {"form": form, "courses": courses})


@login_required
def add_question(request, exam_id):
    """View to add a question to an exam."""
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method == "POST":
        form = QuestionForm(request.POST)
        if form.is_valid():
            question = form.save(commit=False)
            question.exam = exam
            question.save()
            messages.success(request, "✅ Question added successfully!")
            return redirect("exams:detail", exam_id=exam.id)

    else:
        form = QuestionForm()

    return render(request, "exams/add_question.html", {"form": form, "exam": exam})


@login_required
def edit_question(request, question_id):
    """View to edit a question."""
    question = get_object_or_404(Question, id=question_id)

    if request.method == "POST":
        form = QuestionForm(request.POST, instance=question)
        if form.is_valid():
            form.save()
            messages.success(request, "✅ Question updated successfully!")
            return redirect("exams:detail", exam_id=question.exam.id)

    else:
        form = QuestionForm(instance=question)

    return render(request, "exams/edit_question.html", {"form": form, "question": question})


@login_required
def exam_students_grades(request, exam_id):
    """View to display student grades for a specific exam."""
    exam = get_object_or_404(Exam, id=exam_id)
    grades = Grade.objects.filter(exam=exam)

    return render(request, "exams/exam_students_grades.html", {
        "exam": exam,
        "grades": grades
    })


@login_required
def upload_pdf(request, exam_id):
    """Upload a PDF for an exam."""
    exam = get_object_or_404(Exam, id=exam_id)

    if request.method == "POST" and request.FILES.get("pdf_file"):
        # Delete old file if exists
        if exam.pdf_file:
            default_storage.delete(exam.pdf_file.path)

        # Save new file
        exam.pdf_file = request.FILES["pdf_file"]
        exam.save()

        messages.success(request, "✅ PDF uploaded successfully!")
        return redirect("exams:detail", exam_id=exam.id)

    messages.error(request, "⚠️ Please select a valid PDF file.")
    return redirect("exams:detail", exam_id=exam.id)


@login_required
def download_pdf(request, exam_id):
    """Generate a structured answer sheet PDF with proper formatting."""
    exam = get_object_or_404(Exam, id=exam_id)
    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{exam.name}_Bubble_Sheet.pdf"'

    pdf_canvas = canvas.Canvas(response, pagesize=letter)
    width, height = letter

    # **Header Section**
    pdf_canvas.setFont("Helvetica-Bold", 14)
    pdf_canvas.drawString(50, height - 40, "Student: ___________________________")
    pdf_canvas.drawString(50, height - 60, f"Exam: {exam.name}")

    # **Define Positions**
    question_x = 50
    answer_x = width - 250  # **Align answer section fully to the right**
    y = height - 120
    question_number = 1

    # **Ensure Answer Area Border Spans the Entire Right Side**
   # pdf_canvas.setStrokeColor(colors.black)
   # pdf_canvas.setDash(2, 4)  # Dotted Border
    #pdf_canvas.rect(answer_x - 40, 50, 220, height - 180)  # Full right border
    pdf_canvas.setDash()  # Reset to normal line

    for question in exam.questions.all():
        pdf_canvas.setFont("Helvetica", 12)

        # ✅ **Break long text into multiple lines (without numbering each line)**
        wrapped_text = simpleSplit(question.text, "Helvetica", 12, width - 300)
        pdf_canvas.drawString(question_x, y, f"{question_number}. {wrapped_text[0]}")  # First line with number
        for line in wrapped_text[1:]:
            y -= 15
            pdf_canvas.drawString(question_x + 20, y, line)  # Indented without numbering

        # ✅ **Ensure enough space between question & answer**
        y -= 10

        # **Answer area formatting**
        if question.question_type == "MCQ":  # Multiple Choice
            bubble_x = answer_x
            for choice in ["A", "B", "C", "D"]:
                pdf_canvas.circle(bubble_x, y, 8)
                pdf_canvas.drawString(bubble_x - 3, y - 3, choice)
                bubble_x += 30  # Adjust spacing

        elif question.question_type == "TF":  # True/False
            pdf_canvas.circle(answer_x, y, 8)
            pdf_canvas.circle(answer_x + 40, y, 8)
            pdf_canvas.drawString(answer_x - 3, y - 3, "T")
            pdf_canvas.drawString(answer_x + 37, y - 3, "F")

        elif question.question_type == "SA":  # Short Answer
            y -= 20
            pdf_canvas.setDash(2, 4)  # Dotted Box
            pdf_canvas.rect(answer_x, y - 20, 140, 30)
            pdf_canvas.setDash()

        elif question.question_type == "LA":  # Long Answer (Increased Space)
            y -= 80
            pdf_canvas.rect(answer_x, y - 80, 140, 120)

        y -= 60  # Move to next question
        question_number += 1

        if y < 100:  # **New Page Handling**
            pdf_canvas.showPage()
            y = height - 100

    # ✅ **Add 6 Square Bullets around Answer Area**
    bullet_size = 8
    bullet_positions = [
        (answer_x - 45, height - 50),  # Top Left
        (answer_x + 175, height - 50),  # Top Right
        (answer_x - 45, 50),  # Bottom Left
        (answer_x + 175, 50),  # Bottom Right
        (answer_x - 45, (height - 50) / 2),  # Middle Left
        (answer_x + 175, (height - 50) / 2),  # Middle Right
    ]
    for bx, by in bullet_positions:
        pdf_canvas.rect(bx, by, bullet_size, bullet_size, stroke=1, fill=1)

    # ✅ **QR Code Placeholder**
    #pdf_canvas.rect(50, 50, 80, 80)

    # ✅ **Instructions Box (Moved to Left Side)**
    pdf_canvas.rect(50, 50, 200, 80)  # Moved to left side
    pdf_canvas.setFont("Helvetica", 10)
    pdf_canvas.drawString(60, 110, "IMPORTANT:")  # Adjusted for left-side alignment
    pdf_canvas.setFont("Helvetica", 8)
    pdf_canvas.drawString(60, 95, "=> DO NOT MARK OUTSIDE THE CIRCLE.")
    pdf_canvas.drawString(60, 80, "=> USE PENCIL AND ERASE COMPLETELY")
    pdf_canvas.drawString(60, 65, "   TO CHANGE YOUR ANSWER.")

    pdf_canvas.save()
    return response