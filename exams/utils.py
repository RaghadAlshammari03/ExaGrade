from .models import Grade
import io
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth
from django.http import FileResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required

def get_grading_stage_text(exam):
    all_paper_ids = set(exam.student_papers.values_list("id", flat=True))
    graded_paper_ids = set(Grade.objects.filter(exam=exam).values_list("studentpaper_id", flat=True))

    if not graded_paper_ids:
        return "Grade Exam"
    elif all_paper_ids - graded_paper_ids:
        return "Grade New Papers"
    return "Regrade All"

@require_POST
@login_required
def generate_exam_pdf_from_data(request):
    data = request.POST
    questions = extract_questions_from_data(data)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin_bottom = 80
    y = height - 100
    q_number = 1
    page_number = 1
    max_text_width = width - 100

    instructor_name = request.user.username if request.user.is_authenticated else "Instructor"
    course_name = data.get('course_name', 'Course Name')

    def draw_header():
        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(width / 2, height - 40, f"{data.get('exam_name', 'Exam Name')} - Exam Paper")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, "Student Name: ____________________________")
        p.drawString(350, height - 70, "Student ID: ______________________")

    draw_header()
    y = height - 120

    def draw_footer():
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.drawString(50, 20, f"Instructor: {instructor_name} | Course: {course_name}")
        p.drawRightString(width - 50, 20, f"Page {page_number}")
        p.setFillColorRGB(0, 0, 0)

    def next_page():
        nonlocal y, page_number
        draw_footer()
        p.showPage()
        page_number += 1
        draw_header()
        y = height - 120

    def section_header(title, instruction):
        nonlocal y
        if y < 130:
            next_page()
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"■ {title}")
        y -= 16
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.5, 0, 0)
        p.drawString(50, y, f"* {instruction}")
        p.setFillColorRGB(0, 0, 0)
        y -= 20

    def draw_wrapped_text(p, x, y, text, max_width, font="Helvetica", font_size=12, line_height=15):
        p.setFont(font, font_size)
        words = text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if stringWidth(test_line, font, font_size) <= max_width:
                line = test_line
            else:
                p.drawString(x, y, line)
                y -= line_height
                line = word
        if line:
            p.drawString(x, y, line)
            y -= line_height
        return y

    # Questions
    if questions["tf"]:
        section_header("True/False Questions", "Write 'True' or 'False' clearly in the box.")
        for q in questions["tf"]:
            if y < margin_bottom:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {	q['text']} [{q['marks']} marks]", max_text_width)
            y -= 10  
            p.rect(width - 90, y + 5, 35, 15)
            y -= 20 
            q_number += 1

    if questions["mcq"]:
        section_header("Multiple Choice Questions", "Write the letter of the correct option.")
        for q in questions["mcq"]:
            if y < margin_bottom:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            options_line = "    ".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(q['options'])])
            y = draw_wrapped_text(p, 70, y, options_line, max_text_width - 70)
            y -= 20
            p.rect(width - 90, y + 5, 35, 15)
            y -= 20
            q_number += 1

    if questions["short"]:
        section_header("Short Answer Questions", "Write your answer inside the box.")
        for q in questions["short"]:
            if y < margin_bottom + 80:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            p.rect(50, y - 60, width - 100, 60)
            y -= 80
            q_number += 1

    if questions["long"]:
        section_header("Long Answer Questions", "Write your detailed response below.")
        for q in questions["long"]:
            if y < margin_bottom + 140:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            p.rect(50, y - 120, width - 100, 120)
            y -= 140
            q_number += 1

    draw_footer()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, content_type="application/pdf")

def extract_questions_from_data(data):
    tf_questions = [
        {"text": text, "marks": marks, "correct_answer": answer}
        for text, marks, answer in zip(
            data.getlist('tf_questions[]'),
            data.getlist('tf_marks[]'),
            data.getlist('tf_answers[]')
        )
    ]

    short_questions = [
        {"text": text, "marks": marks, "correct_answer": answer}
        for text, marks, answer in zip(
            data.getlist('short_questions[]'),
            data.getlist('short_marks[]'),
            data.getlist('short_correct_answer[]')
        )
    ]

    long_questions = [
        {"text": text, "marks": marks, "correct_answer": answer}
        for text, marks, answer in zip(
            data.getlist('long_questions[]'),
            data.getlist('long_marks[]'),
            data.getlist('long_correct_answer[]')
        )
    ]

    mcq_questions = []
    mcq_texts = data.getlist('mcq_questions[]')
    mcq_marks = data.getlist('mcq_marks[]')
    mcq_options_1 = data.getlist('mcq_options_1[]')
    mcq_options_2 = data.getlist('mcq_options_2[]')
    mcq_options_3 = data.getlist('mcq_options_3[]')
    mcq_options_4 = data.getlist('mcq_options_4[]')
    mcq_answers = data.getlist('mcq_answers[]')

    for i in range(len(mcq_texts)):
        mcq_questions.append({
            "text": mcq_texts[i],
            "marks": mcq_marks[i],
            "options": [
                mcq_options_1[i],
                mcq_options_2[i],
                mcq_options_3[i],
                mcq_options_4[i],
            ],
            "correct_answer": mcq_answers[i],
        })

    return {
        "tf": tf_questions,
        "mcq": mcq_questions,
        "short": short_questions,
        "long": long_questions,
    }

@require_POST
@login_required
def generate_answered_pdf_from_data(request):
    data = request.POST
    questions = extract_questions_from_data(data)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin_bottom = 80
    y = height - 100
    q_number = 1
    page_number = 1
    max_text_width = width - 100

    instructor_name = request.user.username if request.user.is_authenticated else "Instructor"
    course_name = data.get('course_name', 'Course Name')

    def draw_header():
        p.setFont("Helvetica-Bold", 18)
        p.drawCentredString(width / 2, height - 40, f"{data.get('exam_name', 'Exam Name')} - Answered Module")
        p.setFont("Helvetica", 12)
        p.drawString(50, height - 70, "Student Name: ____________________________")
        p.drawString(350, height - 70, "Student ID: ______________________")

    draw_header()
    y = height - 120

    def draw_footer():
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.drawString(50, 20, f"Instructor: {instructor_name} | Course: {course_name}")
        p.drawRightString(width - 50, 20, f"Page {page_number}")
        p.setFillColorRGB(0, 0, 0)

    def next_page():
        nonlocal y, page_number
        draw_footer()
        p.showPage()
        page_number += 1
        draw_header()
        y = height - 120

    def section_header(title, instruction):
        nonlocal y
        if y < 130:
            next_page()
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"■ {title}")
        y -= 16
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.5, 0, 0)
        p.drawString(50, y, f"* {instruction}")
        p.setFillColorRGB(0, 0, 0)
        y -= 20

    def draw_wrapped_text(p, x, y, text, max_width, font="Helvetica", font_size=12, line_height=15, color=(0, 0, 0)):
        p.setFont(font, font_size)
        p.setFillColorRGB(*color)
        words = text.split()
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if stringWidth(test_line, font, font_size) <= max_width:
                line = test_line
            else:
                p.drawString(x, y, line)
                y -= line_height
                line = word
        if line:
            p.drawString(x, y, line)
            y -= line_height
        p.setFillColorRGB(0, 0, 0)
        return y

    draw_header()

    # True/False
    if questions["tf"]:
        section_header("True/False Questions", "Write 'True' or 'False' clearly in the box.")
        for q in questions["tf"]:
            if y < margin_bottom + 40:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {	q['text']} [{q['marks']} marks]", max_text_width)
            y -= 10  
            p.rect(width - 90, y + 5, 35, 15)
            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.2, 0.4, 0.9)
            p.drawString(width - 85, y + 7, q.get('correct_answer', '')[:15])
            p.setFillColorRGB(0, 0, 0)
            y -= 20 
            q_number += 1

    # MCQ
    if questions["mcq"]:
        section_header("Multiple Choice Questions", "Write the letter of the correct option.")
        for q in questions["mcq"]:
            if y < margin_bottom + 60:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            options_line = "    ".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(q['options'])])
            y = draw_wrapped_text(p, 70, y, options_line, max_text_width - 70)
            y -= 20
            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.2, 0.4, 0.9)
            p.drawString(width - 85, y + 7, q.get('correct_answer', '')[:15])
            p.setFillColorRGB(0, 0, 0)
            p.rect(width - 90, y + 5, 35, 15)
            y -= 30
            q_number += 1

    # Short Answer
    if questions["short"]:
        section_header("Short Answer Questions", "Write your answer inside the box.")
        for q in questions["short"]:
            if y < margin_bottom + 90:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            p.rect(50, y - 60, width - 100, 60)
            y = draw_wrapped_text(p, 55, y - 20, q.get('correct_answer', '') or "", width - 110,
                                  font="Helvetica", font_size=11, color=(0.2, 0.4, 0.9))
            y -= 50
            q_number += 1

    # Long Answer
    if questions["long"]:
        section_header("Long Answer Questions", "Write your detailed response below.")
        for q in questions["long"]:
            if y < margin_bottom + 150:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            p.rect(50, y - 120, width - 100, 120)
            y = draw_wrapped_text(p, 55, y - 20, q.get('correct_answer', '') or "", width - 110,
                                  font="Helvetica", font_size=11, color=(0.2, 0.4, 0.9))
            y -= 80
            q_number += 1

    draw_footer()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, content_type="application/pdf")