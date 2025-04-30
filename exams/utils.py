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
    from .utils import extract_questions_from_data
    data = request.POST
    questions = extract_questions_from_data(data)
    show_fields = request.POST.getlist("header_fields")
    long_lines = data.getlist("long_lines[]")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    max_text_width = width - 100
    margin_bottom = 80
    y = height - 100
    q_number = 1
    page_number = 1

    instructor_name = request.user.username if request.user.is_authenticated else "Instructor"
    course_name = data.get('course_name', 'Course Name')

    def draw_header():
        nonlocal y
        y_start = height - 40

        if "exam_name" in show_fields:
            p.setFont("Helvetica-Bold", 18)
            p.drawCentredString(width / 2, y_start, f"{data.get('exam_name', 'Exam Name')} - Exam Paper")
            y_start -= 30

        p.setFont("Helvetica", 12)
        if "student_name" in show_fields or "student_id" in show_fields:
            line = ""
            if "student_name" in show_fields:
                line += "Student Name: ____________________________"
            if "student_id" in show_fields:
                if line:
                    line += "     "
                line += "Student ID: ____________________"
            p.drawString(50, y_start, line)
            y_start -= 30

        if "paper_number" in show_fields:
            p.drawString(50, y_start, "Student Number: ____________________________")
            y_start -= 40

        y = y_start

    def draw_footer():
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        footer_left = ""
        if "instructor_name" in show_fields:
            footer_left += f"Instructor: {instructor_name}"
        if "course_name" in show_fields:
            if footer_left:
                footer_left += " | "
            footer_left += f"Course: {course_name}"
        p.drawString(50, 20, footer_left)
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

    draw_header()

    # True/False
    if questions["tf"]:
        section_header("True/False Questions", "Write 'True' or 'False' clearly in the box.")
        for q in questions["tf"]:
            estimated_height = 50
            if y < margin_bottom + estimated_height:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            y -= 10
            p.rect(width - 90, y + 5, 35, 15)
            y -= 20
            q_number += 1

    # MCQ
    if questions["mcq"]:
        section_header("Multiple Choice Questions", "Write the letter of the correct option.")
        for q in questions["mcq"]:
            estimated_height = 70
            if y < margin_bottom + estimated_height:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            options_line = "    ".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(q["options"])])
            y = draw_wrapped_text(p, 70, y, options_line, max_text_width - 70)
            y -= 10
            p.rect(width - 90, y + 5, 35, 15)
            y -= 20
            q_number += 1

    # Short Answer
    if questions["short"]:
        section_header("Short Answer Questions", "Write your answer inside the box.")
        for q in questions["short"]:
            box_height = 80
            estimated_height = box_height + 40  

            if y < margin_bottom + estimated_height:
                next_page()

            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)

            p.rect(50, y - box_height, width - 100, box_height)

            y -= box_height + 20  
            q_number += 1

    # Long Answer
    if questions["long"]:
        section_header("Long Answer Questions", "Write your detailed response below.")
        for i, q in enumerate(questions["long"]):
            lines = int(long_lines[i]) if i < len(long_lines) else 6
            height_box = lines * 15 + 30
            estimated_height = height_box + 40
            if y < margin_bottom + estimated_height:
                next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_text_width)
            p.rect(50, y - height_box, width - 100, height_box)
            y -= height_box + 20
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
    from .utils import extract_questions_from_data
    data = request.POST
    questions = extract_questions_from_data(data)
    show_fields = data.getlist("header_fields")
    long_lines = data.getlist("long_lines[]")

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    max_width = width - 100
    margin_bottom = 80
    y = height - 100
    q_number = 1
    page_number = 1

    instructor_name = request.user.username if request.user.is_authenticated else "Instructor"
    course_name = data.get('course_name', 'Course Name')

    def draw_header():
        nonlocal y
        y_start = height - 40

        if "exam_name" in show_fields:
            p.setFont("Helvetica-Bold", 18)
            p.drawCentredString(width / 2, y_start, f"{data.get('exam_name', 'Exam Name')} - Answered Module")
            y_start -= 30

        p.setFont("Helvetica", 12)
        line = ""
        if "student_name" in show_fields:
            line += "Student Name: ____________________________"
        if "student_id" in show_fields:
            if line:
                line += "     "
            line += "Student ID: ____________________"
        if line:
            p.drawString(50, y_start, line)
            y_start -= 30

        if "paper_number" in show_fields:
            p.drawString(50, y_start, "Student Number: ____________________________")
            y_start -= 30

        y = y_start

    def draw_footer():
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        footer = []
        if "instructor_name" in show_fields:
            footer.append(f"Instructor: {instructor_name}")
        if "course_name" in show_fields:
            footer.append(f"Course: {course_name}")
        p.drawString(50, 20, " | ".join(footer))
        p.drawRightString(width - 50, 20, f"Page {page_number}")
        p.setFillColorRGB(0, 0, 0)

    def next_page():
        nonlocal y, page_number
        draw_footer()
        p.showPage()
        page_number += 1
        draw_header()
        y = height - 120

    def wrap_text(p, x, y, text, max_width, font="Helvetica", font_size=12, line_height=15, color=(0, 0, 0)):
        p.setFont(font, font_size)
        p.setFillColorRGB(*color)
        words = text.split()
        line = ""
        for word in words:
            test = f"{line} {word}".strip()
            if stringWidth(test, font, font_size) <= max_width:
                line = test
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

    # True/False Questions
    if questions["tf"]:
        for q in questions["tf"]:
            if y < margin_bottom + 50:
                next_page()
            y = wrap_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_width)
            y -= 10
            p.rect(width - 90, y + 5, 35, 15)
            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.2, 0.4, 0.9)
            p.drawString(width - 85, y + 7, q.get('correct_answer', '')[:15])
            p.setFillColorRGB(0, 0, 0)
            y -= 20
            q_number += 1

    # MCQ Questions
    if questions["mcq"]:
        for q in questions["mcq"]:
            if y < margin_bottom + 70:
                next_page()
            y = wrap_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_width)
            options_line = "    ".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(q["options"])])
            y = wrap_text(p, 70, y, options_line, max_width - 70)
            y -= 10
            p.rect(width - 90, y + 5, 35, 15)
            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.2, 0.4, 0.9)
            p.drawString(width - 85, y + 7, q.get('correct_answer', '')[:15])
            p.setFillColorRGB(0, 0, 0)
            y -= 30
            q_number += 1

    # Short Answer Questions
    if questions["short"]:
        for q in questions["short"]:
            box_height = 80
            if y < margin_bottom + box_height + 40:
                next_page()
            y = wrap_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_width)
            p.rect(50, y - box_height, width - 100, box_height)
            y = wrap_text(p, 55, y - 20, q.get('correct_answer', ''), width - 110,
                          font="Helvetica", font_size=11, color=(0.2, 0.4, 0.9))
            y -= box_height - 40
            y -= 20
            q_number += 1

    # Long Answer Questions
    if questions["long"]:
        for i, q in enumerate(questions["long"]):
            lines = int(long_lines[i]) if i < len(long_lines) else 6
            height_box = lines * 15 + 30
            if y < margin_bottom + height_box + 40:
                next_page()
            y = wrap_text(p, 50, y, f"{q_number}. {q['text']} [{q['marks']} marks]", max_width)
            p.rect(50, y - height_box, width - 100, height_box)
            y = wrap_text(p, 55, y - 20, q.get('correct_answer', ''), width - 110,
                          font="Helvetica", font_size=11, color=(0.2, 0.4, 0.9))
            y -= height_box - 40
            y -= 20
            q_number += 1

    draw_footer()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, content_type="application/pdf")