import io,json,re
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import FileResponse
from django.conf import settings
from django.views.decorators.http import require_POST
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
from django.http import JsonResponse
from .models import Exam
from exa_ai.grading import grade_answer, parse_score_and_feedback
from users.models import CustomUser
from .models import Exam, Grade, StudentPaper, Question
from courses.models import Course
from reportlab.pdfbase.pdfmetrics import stringWidth
from django.views.decorators.csrf import csrf_exempt
from .models import FlaggedIssue
from utils.utils import extract_text_from_pdf, extract_name_and_id
from django.core.mail import EmailMessage
from django.http import FileResponse
from .utils import get_grading_stage_text

@login_required
def exam_list_view(request):
    if request.user.is_instructor:
        exams = Exam.objects.filter(course__in=request.user.courses.all())
    else:
        exams = Exam.objects.filter(course__in=request.user.enrolled_courses.all())
    return render(request, "exams/exam_list.html", {"exams": exams})

@login_required
def exam_detail_view(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user.is_instructor:
        context = {}
        student_papers = StudentPaper.objects.filter(exam=exam, merged_into__isnull=True)
        enrolled_students = set(exam.course.students.all())
        grades = Grade.objects.filter(exam=exam)
        graded_paper_ids = set(grades.values_list("studentpaper_id", flat=True))
        has_graded_papers = grades.exists()

        paper_data = []
        for paper in student_papers:
            if not paper.text and paper.file and os.path.exists(paper.file.path):
                paper.text = extract_text_from_pdf(paper.file.path)
                paper.save()

            text = paper.text or ""
            extracted_name, extracted_id = extract_name_and_id(text)

            if not paper.manual_name and not paper.student:
                if extracted_name and extracted_name.lower() != "empty":
                    paper.manual_name = extracted_name
                    paper.save()

            if not paper.manual_id and not paper.student:
                if extracted_id:
                    paper.manual_id = extracted_id
                    paper.save()

            matched_student = paper.student
            if not paper.student and paper.manual_id:
                try:
                    matched_student = CustomUser.objects.get(student_id=paper.manual_id)
                    paper.student = matched_student
                    paper.save()
                except CustomUser.DoesNotExist:
                    matched_student = None

            is_enrolled_and_matched = matched_student in enrolled_students
            grade = Grade.objects.filter(studentpaper=paper).first()
            display_name = paper.manual_name.strip() if paper.manual_name else (
                matched_student.get_full_name() if matched_student else "Empty"
            )

            merged_children = paper.merged_papers.all()
            merged_files = []
            for idx, m in enumerate(merged_children, start=2):
                merged_files.append({
                    "label": f"Paper {idx}",
                    "url": m.file.url,
                    "text": m.text,
                    "id": m.id,
                })

            paper.is_merged = paper.merged_papers.exists() or paper.merged_into is not None

            def split_feedback_into_questions(feedback_text):
                if not feedback_text:
                    return []

                question_blocks = re.split(r"(Question \d+:)", feedback_text)
                result = []
                i = 1

                while i < len(question_blocks):
                    if question_blocks[i].startswith("Question"):
                        title = question_blocks[i].strip()
                        content = question_blocks[i + 1].strip() if i + 1 < len(question_blocks) else ""

                        content = re.sub(r"Student Answer:.*?(AI Feedback:)?", "", content, flags=re.DOTALL).strip()

                        result.append({
                            "question": title,
                            "feedback": content,
                            "type": "AI"
                        })
                        i += 2
                    else:
                        i += 1

                return result

            paper_data.append({
                "id": paper.id,
                "file_url": paper.file.url,
                "student_name": display_name,
                "grade": grade.grade if grade else "not graded yet",
                "manual_override": grade.manual_override if grade and grade.manual_override else None,
                "feedback": grade.feedback if grade else None,
                "extracted_text": text,
                "flagged_issues": paper.flagged_issues.filter(resolved=False),
                "student_id": paper.manual_id or "—",
                "manual_id": paper.manual_id,
                "instructor_feedback": paper.instructor_feedback or "",
                "paper": paper,
                "is_enrolled_and_matched": is_enrolled_and_matched,
                "merged_files": merged_files,
                "badges": list(filter(None, [
                    {"text": "Ungraded", "style": "bg-yellow-100 text-yellow-800"} if paper.id not in graded_paper_ids else None,
                    {"text": "Name Missing", "style": "bg-red-100 text-red-700"} if not paper.manual_name and not matched_student else None,
                    {"text": "ID Missing", "style": "bg-orange-100 text-orange-700"} if not paper.manual_id else None,
                    {"text": "⚠️ Review Needed", "style": "bg-red-100 text-red-700"} if paper.flagged_issues.filter(resolved=False).exists() else None,
                    {"text": "Not Enrolled", "style": "bg-gray-100 text-gray-600 italic"} if not is_enrolled_and_matched else None,
                    {"text": "Enrolled", "style": "bg-green-100 text-green-700"} if is_enrolled_and_matched else None,
                    {"text": "Merged", "style": "bg-purple-100 text-purple-800"} if paper.is_merged else None,
                ])),
                "graded_questions": split_feedback_into_questions(grade.feedback) if grade and grade.feedback else [],
            })

        exam.update_status()

        context.update({
            "exam": exam,
            "paper_data": paper_data,
            "student_papers": student_papers,
            "grades": grades,
            "send_options": ["Grades", "AI Feedback", "Instructor Feedback"],
            "grading_button_text": get_grading_stage_text(exam),
            "has_graded_papers": has_graded_papers,
            "grade_chart_data": json.dumps([
                {
                    "name": paper["student_name"],
                    "score": float(paper["manual_override"] or paper["grade"])
                }
                for paper in paper_data
                if (paper["manual_override"] or paper["grade"]) not in ["", None, "not graded yet"]
            ]),
            "paper_data_json": json.dumps(paper_data, default=str),
        })        

        return render(request, "exams/exam_detail.html", context)

    else:
        paper = StudentPaper.objects.filter(exam=exam, student=request.user).first()
        if not paper:
            full_name = f"{request.user.first_name} {request.user.last_name}".strip().lower()
            paper = StudentPaper.objects.filter(exam=exam, manual_name__iexact=full_name).first()

        grade = Grade.objects.filter(studentpaper=paper, exam=exam).first()

        return render(request, "exams/exam_detail_student.html", {
            "exam": exam,
            "paper": paper,
            "grade": grade,
            "student_score": grade.manual_override if grade and grade.manual_override else grade.grade if grade else None,
            "ai_feedback": grade.feedback if grade else "",
            "instructor_feedback": paper.instructor_feedback if paper else "",
        })


@login_required
def add_or_edit_exam(request):
    if not request.user.is_instructor:
        messages.error(request, "⚠️ Only instructors can create or edit exams.")
        return redirect("exams:list")

    exam_to_edit = None
    questions_by_type = {}
    edit_mode = request.GET.get("edit")

    if edit_mode:
        exam_to_edit = get_object_or_404(Exam, id=edit_mode, instructor=request.user)
        all_questions = Question.objects.filter(exam=exam_to_edit)

        mcq_questions = all_questions.filter(question_type='mcq')
        for q in mcq_questions:
            q.option_list = q.mcq_options.split(",") if q.mcq_options else ["", "", "", ""]

        questions_by_type = {
            'true_false': all_questions.filter(question_type='true_false'),
            'mcq': mcq_questions,
            'short_answer': all_questions.filter(question_type='short_answer'),
            'long_answer': all_questions.filter(question_type='long_answer'),
        }

    if request.method == "POST":
        exam_name = request.POST.get("exam_name")
        course_id = request.POST.get("course")
        total_marks = request.POST.get("total_marks")
        exam_time = request.POST.get("exam_time")

        if not exam_name or not course_id or not total_marks:
            messages.error(request, "⚠️ Please fill in all required fields.")
            return redirect(request.path_info)

        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            messages.error(request, "❌ Invalid course.")
            return redirect("exams:add")

        # Create or update exam
        if exam_to_edit:
            exam = exam_to_edit
            exam.name = exam_name
            exam.course = course
            exam.total_marks = total_marks
            exam.duration_minutes = exam_time or 0
            exam.save()
            Question.objects.filter(exam=exam).delete()
        else:
            exam = Exam.objects.create(
                name=exam_name,
                course=course,
                instructor=request.user,
                total_marks=total_marks,
                duration_minutes=exam_time or 0
            )

        # True/False
        tf_questions = request.POST.getlist('tf_questions[]')
        tf_answers = request.POST.getlist('tf_answers[]')
        tf_marks = request.POST.getlist('tf_marks[]')
        for q, a, m in zip(tf_questions, tf_answers, tf_marks):
            if not q or not a or not m:
                messages.error(request, "⚠️ Please fill in all fields for each True/False question.")
                return redirect(request.path_info)
            Question.objects.create(
                exam=exam,
                question_type='true_false',
                text=q,
                correct_answer=a,
                marks=m
            )

        # MCQ
        mcq_questions = request.POST.getlist('mcq_questions[]')
        opt1 = request.POST.getlist('mcq_options_1[]')
        opt2 = request.POST.getlist('mcq_options_2[]')
        opt3 = request.POST.getlist('mcq_options_3[]')
        opt4 = request.POST.getlist('mcq_options_4[]')
        answers = request.POST.getlist('mcq_answers[]')
        mcq_marks = request.POST.getlist('mcq_marks[]')
        for i in range(len(mcq_questions)):
            if not mcq_questions[i] or not answers[i] or not mcq_marks[i] or not opt1[i] or not opt2[i] or not opt3[i] or not opt4[i]:
                messages.error(request, "⚠️ Please fill in all fields for each MCQ question.")
                return redirect(request.path_info)
            Question.objects.create(
                exam=exam,
                question_type='mcq',
                text=mcq_questions[i],
                mcq_options=",".join([opt1[i], opt2[i], opt3[i], opt4[i]]),
                correct_answer=answers[i],
                marks=mcq_marks[i]
            )

        # Short Answer
        short_questions = request.POST.getlist('short_questions[]')
        short_answers = request.POST.getlist('short_correct_answer[]')
        short_marks = request.POST.getlist('short_marks[]')
        short_eval_types = request.POST.getlist('short_eval_type[]')
        short_custom_notes = request.POST.getlist('short_custom_eval[]')

        for q, a, m, et, custom_note in zip(short_questions, short_answers, short_marks, short_eval_types, short_custom_notes):
            if not q or not a or not m or not et:
                messages.error(request, "⚠️ Please fill in all fields for each Short Answer question.")
                return redirect(request.path_info)
            Question.objects.create(
                exam=exam,
                question_type='short_answer',
                text=q,
                correct_answer=a,
                marks=m,
                eval_type=et,
                custom_eval=custom_note if et == 'custom' else ''
            )

        # Long Answer
        long_questions = request.POST.getlist('long_questions[]')
        long_answers = request.POST.getlist('long_correct_answer[]')
        long_marks = request.POST.getlist('long_marks[]')
        long_eval_types = request.POST.getlist('long_eval_type[]')
        long_custom_notes = request.POST.getlist('long_custom_eval[]')

        for q, a, m, et, note in zip(long_questions, long_answers, long_marks, long_eval_types, long_custom_notes):
            if not q or not a or not m or not et:
                messages.error(request, "⚠️ Please fill in all fields for each Long Answer question.")
                return redirect(request.path_info)
            Question.objects.create(
                exam=exam,
                question_type='long_answer',
                text=q,
                correct_answer=a,
                marks=m,
                eval_type=et,
                custom_eval=note if et == "custom" else ""
            )

        messages.success(request, f"✅ Exam '{exam.name}' {'updated' if exam_to_edit else 'created'} successfully!")
        return redirect("exams:list")

    courses = Course.objects.filter(instructor=request.user)
    return render(request, "exams/add_exam.html", {
        "courses": courses,
        "exam": exam_to_edit,
        "questions_by_type": questions_by_type,
    })

@require_POST
@login_required
def grade_exam(request, exam_id):
    from utils.parser import group_papers_by_id
    from exa_ai.grading import grade_answer, parse_score_and_feedback
    from exams.models import FlaggedIssue

    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
        messages.error(request, "⚠️ You are not authorized to grade this exam.")
        return redirect("exams:detail", exam_id=exam.id)

    # ✅ Read grading mode from POST data
    mode = request.POST.get("mode", "").lower()  # 'new', 'regrade', or ''

    grouped, _ = group_papers_by_id(exam)
    questions = exam.questions.all()
    graded_results = []

    for group_key, papers in grouped.items():
        combined_text = "\n\n".join([p.text or "" for p in papers])
        student_id = papers[0].manual_id or ""
        student = CustomUser.objects.filter(student_id=student_id).first() if student_id else None

        already_graded = Grade.objects.filter(exam=exam, studentpaper__in=papers).exists()
        needs_regrading = any(p.needs_regrading for p in papers)

        # ✅ MODE-BASED GRADING CONDITIONS
        if mode == "new":
            if not needs_regrading:
                continue  # Only grade flagged/merged papers
        elif mode == "regrade":
            Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()
            FlaggedIssue.objects.filter(studentpaper__in=papers).delete()
        else:
            if already_graded and not needs_regrading:
                continue  # Default: skip already graded

        # ✅ Clear before regrading (skip if mode is default and grading fresh)
        if mode in ["regrade", "new"] or needs_regrading:
            Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()
            FlaggedIssue.objects.filter(studentpaper__in=papers).delete()

        total_score = 0
        feedback_parts = []
        question_number = 1

        for q in questions:
            result = grade_answer(
                q.text, combined_text, q.correct_answer, q.marks,
                eval_type=q.eval_type or "strict",
                custom_note=q.custom_eval or "",
                question_type=q.question_type
            )
            score, feedback, needs_attention = parse_score_and_feedback(result, q.marks, question_number)

            if needs_attention:
                for p in papers:
                    FlaggedIssue.objects.create(
                        studentpaper=p,
                        question=q,
                        flagged_text=combined_text,
                        manual_score=None,
                        resolved=False
                    )

            total_score += score
            feedback_parts.append(feedback)
            question_number += 1

        Grade.objects.create(
            student=student,
            studentpaper=papers[0],
            exam=exam,
            grade=str(total_score),
            feedback="<br><br>".join(feedback_parts),
        )

        for p in papers:
            p.is_merged = len(papers) > 1
            p.needs_regrading = False
            p.save()

        graded_results.append({
            "student": student.get_full_name() if student else group_key,
            "score": total_score
        })

    exam.update_status()

    if request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JsonResponse({
            "success": True,
            "results": graded_results,
            "total": len(graded_results),
        })

    messages.success(request, "✅ Grading complete!")
    return redirect("exams:detail", exam_id=exam.id)

@require_POST
@login_required
def grade_individual_student(request, exam_id, paper_id):
    from exa_ai.grading import grade_answer, parse_score_and_feedback

    exam = get_object_or_404(Exam, id=exam_id)
    paper = get_object_or_404(StudentPaper, id=paper_id, exam=exam)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    # 🧠 Only grade this specific paper's extracted text
    text_to_grade = paper.text or ""
    student_id = paper.manual_id or ""
    student = CustomUser.objects.filter(student_id=student_id).first() if student_id else None

    # Clean up previous grades/flags
    Grade.objects.filter(exam=exam, studentpaper=paper).delete()
    FlaggedIssue.objects.filter(studentpaper=paper).delete()

    total_score = 0
    feedback_parts = []
    q_number = 1
    questions = exam.questions.all()

    for q in questions:
        result = grade_answer(
            q.text, text_to_grade, q.correct_answer, q.marks,
            eval_type=q.eval_type or "strict",
            custom_note=q.custom_eval or "",
            question_type=q.question_type
        )
        score, feedback, needs_attention = parse_score_and_feedback(result, q.marks, q_number)

        if needs_attention:
            FlaggedIssue.objects.create(
                studentpaper=paper,
                question=q,
                flagged_text=text_to_grade,
                manual_score=None,
                resolved=False
            )

        total_score += score
        feedback_parts.append(feedback)
        q_number += 1

    # ✅ Save feedback for this paper only
    Grade.objects.create(
        student=student,
        studentpaper=paper,
        exam=exam,
        grade=str(total_score),
        feedback="<br><br>".join(feedback_parts)
    )

    paper.needs_regrading = False
    paper.save()

    exam.update_status()
    messages.success(request, f"✅ Graded: {student.get_full_name() if student else 'Unmatched'}")
    return redirect("exams:detail", exam_id=exam.id)

@require_POST
@login_required
def merge_papers_by_id(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    student_id = request.POST.get("student_id", "").strip()
    if not student_id:
        return JsonResponse({"error": "Missing student ID"}, status=400)

    papers = StudentPaper.objects.filter(exam=exam, manual_id=student_id)
    if papers.count() < 2:
        return JsonResponse({"error": "Not enough papers to merge"}, status=400)

    for paper in papers:
        paper.is_merged = True
        paper.needs_regrading = True
        paper.save()

    Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()

    return JsonResponse({"success": True, "message": f"Merged {papers.count()} papers for ID: {student_id}"})


@require_POST
@login_required
def unmerge_papers_by_id(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    student_id = request.POST.get("student_id", "").strip()
    if not student_id:
        return JsonResponse({"error": "Missing student ID"}, status=400)

    papers = StudentPaper.objects.filter(exam=exam, manual_id=student_id)
    for paper in papers:
        paper.is_merged = False
        paper.needs_regrading = True
        paper.save()

    Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()

    return JsonResponse({"success": True, "message": f"Unmerged {papers.count()} papers for ID: {student_id}"})


@require_POST
@login_required
def merge_papers(request, exam_id):
    print("=== DEBUG: merge request POST ===")
    print("POST keys:", request.POST.keys())
    print("paper_ids raw:", request.POST.getlist("paper_ids"))
    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    paper_ids = request.POST.getlist('paper_ids')
    if len(paper_ids) < 2:
        return JsonResponse({"success": False, "error": "Select at least 2 papers to merge."}, status=400)

    papers = StudentPaper.objects.filter(id__in=paper_ids, exam=exam)
    ids = set(p.manual_id for p in papers)
    names = set((p.manual_name or "").strip().lower() for p in papers)
    raw_names = set(p.manual_name for p in papers)


    if len(ids) > 1:
        return JsonResponse({
            "success": False,
            "error": "Cannot merge: Student IDs do not match."
        }, status=200)  

    if len(names) > 1:
        return JsonResponse({
            "success": False,
            "name_conflict": True,
            "name_options": list(raw_names),
            "paper_ids": paper_ids
        })

    base_paper = papers.first()
    combined_text = "\n\n".join(p.text or "" for p in papers)

    for p in papers:
        if p != base_paper:
            p.is_merged = True
            p.merged_into = base_paper
            p.save()

    base_paper.text = combined_text
    base_paper.is_merged = len(papers) > 1
    base_paper.merged_into = None
    base_paper.needs_regrading = True
    base_paper.save()

    Grade.objects.filter(studentpaper__in=papers, exam=exam).delete()
    for p in papers:
        p.instructor_feedback = ""
        p.manual_feedback = ""
        p.save()

    exam.update_status()
    return JsonResponse({"success": True})


@require_POST
@login_required
def unmerge_paper(request, paper_id):
    paper = get_object_or_404(StudentPaper, id=paper_id)
    if request.user != paper.exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    merged_children = paper.merged_papers.all()
    for child in merged_children:
        child.is_merged = False
        child.merged_into = None
        child.manual_name = paper.manual_name  
        child.save()

    paper.is_merged = False
    paper.merged_into = None
    paper.save()

    Grade.objects.filter(studentpaper=paper).delete()
    paper.exam.update_status()
    return JsonResponse({"success": True})


@require_POST
@login_required
def resolve_name_conflict_merge(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    paper_ids = request.POST.getlist("paper_ids[]")
    resolved_name = request.POST.get("resolved_name", "").strip()

    if not resolved_name or not paper_ids:
        return JsonResponse({"success": False, "error": "Missing data"})

    paper_ids_int = list(map(int, paper_ids))
    papers = StudentPaper.objects.filter(id__in=paper_ids_int, exam=exam)
    base_paper = papers.first()
    combined_text = "\n\n".join(p.text or "" for p in papers)

    for p in papers:
        if p != base_paper:
            p.is_merged = True
            p.merged_into = base_paper
            p.save()

    base_paper.text = combined_text
    for p in papers:
        p.manual_name = resolved_name
        p.save()
    base_paper.is_merged = len(papers) > 1
    base_paper.merged_into = None
    base_paper.needs_regrading = True
    base_paper.save()

    Grade.objects.filter(studentpaper__in=papers, exam=exam).delete()
    for p in papers:
        p.instructor_feedback = ""
        p.manual_feedback = ""
        p.save()

    exam.update_status()
    return JsonResponse({"success": True})

@login_required
def exam_students_grades(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_instructor:
        messages.error(request, "⚠️ You are not authorized to view student grades.")
        return redirect("exams:list")
    grades = Grade.objects.filter(exam=exam)
    return render(request, "exams/exam_students_grades.html", {
        "exam": exam,
        "grades": grades
    })

@login_required
def download_answer_sheet(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    questions = Question.objects.filter(exam=exam)

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    p.setFont("Helvetica-Bold", 14)

    y = 750
    p.drawString(200, y, f"Answer Sheet for {exam.name}")
    y -= 30

    for idx, question in enumerate(questions, 1):
        p.setFont("Helvetica", 12)
        p.drawString(50, y, f"{idx}. {question.text}")
        y -= 20
        if question.question_type == "mcq":
            p.setFont("Helvetica", 11)
            for option in question.get_mcq_options():
                p.drawString(70, y, f"• {option}")
                y -= 15
        y -= 30
        if y < 50:
            p.showPage()
            y = 750

    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{exam.name}_AnswerSheet.pdf")

@require_POST
@login_required
def generate_exam_pdf(request, exam_id):
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

    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    margin_bottom = 80
    y = height - 100
    q_number = 1
    page_number = 1
    max_text_width = width - 100

    def draw_footer():
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.drawString(50, 20, f"Instructor: {exam.instructor.username}  |  Course: {exam.course.name}")
        p.drawRightString(width - 50, 20, f"Page {page_number}")
        p.setFillColorRGB(0, 0, 0)

    def next_page():
        nonlocal y, page_number
        draw_footer()
        p.showPage()
        page_number += 1
        y = height - 100

    def section_header(title, instruction):
        nonlocal y
        if y < 130: next_page()
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"■ {title}")
        y -= 16
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.5, 0, 0)
        p.drawString(50, y, f"* {instruction}")
        p.setFillColorRGB(0, 0, 0)
        y -= 20

    # Header
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, height - 50, f"{exam.name} - Exam Paper")
    p.setFont("Helvetica", 12)
    p.drawString(50, height - 80, "Student Name: ____________________________")
    p.drawString(350, height - 80, "Student ID: ______________________")
    y = height - 120

    grouped = {
        "true_false": [],
        "mcq": [],
        "short_answer": [],
        "long_answer": []
    }
    for q in questions:
        grouped[q.question_type].append(q)

    if grouped["true_false"]:
        section_header("True/False Questions", "Write 'True' or 'False' clearly in the box.")
        for q in grouped["true_false"]:
            if y < margin_bottom + 40: next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            p.rect(width - 90, y + 5, 35, 15)
            y -= 20
            q_number += 1

    if grouped["mcq"]:
        section_header("Multiple Choice Questions", "Write the letter of the correct option.")
        for q in grouped["mcq"]:
            if y < margin_bottom + 55: next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            opt_line = "    ".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(q.get_mcq_options())])
            y = draw_wrapped_text(p, 70, y, opt_line, max_text_width)
            p.rect(width - 90, y + 5, 35, 15)
            y -= 20
            q_number += 1

    if grouped["short_answer"]:
        section_header("Short Answer Questions", "Write your answer inside the box.")
        for q in grouped["short_answer"]:
            if y < margin_bottom + 90: next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            p.setDash(1, 2)
            p.rect(50, y - 60, width - 100, 60)
            p.setDash()
            y -= 80
            q_number += 1

    if grouped["long_answer"]:
        section_header("Long Answer Questions", "Write your detailed response below.")
        for q in grouped["long_answer"]:
            if y < margin_bottom + 150: next_page()
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            p.rect(50, y - 120, width - 100, 120)
            y -= 140
            q_number += 1

    draw_footer()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{exam.name}_PaperExam.pdf")

@require_POST
@login_required
def generate_answered_pdf(request, exam_id):

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

    def estimate_height(text, max_width, font="Helvetica", font_size=12, line_height=15):
        words = text.split()
        lines = 1
        line = ""
        for word in words:
            test_line = f"{line} {word}".strip()
            if stringWidth(test_line, font, font_size) <= max_width:
                line = test_line
            else:
                lines += 1
                line = word
        return lines * line_height

    exam = get_object_or_404(Exam, id=exam_id)
    questions = exam.questions.all()

    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    max_text_width = width - 100
    top_margin = 60
    bottom_margin = 80
    y = height - top_margin
    q_number = 1
    page_num = 1

    def draw_footer():
        p.setFont("Helvetica-Oblique", 9)
        p.setFillColorRGB(0.4, 0.4, 0.4)
        p.drawString(50, 20, f"Instructor: {exam.instructor.username}  |  Course: {exam.course.name}")
        p.drawRightString(width - 50, 20, f"Page {page_num}")
        p.setFillColorRGB(0, 0, 0)

    def next_page():
        nonlocal y, page_num
        draw_footer()
        p.showPage()
        page_num += 1
        y = height - top_margin

    def ensure_space(required_height):
        nonlocal y
        if y - required_height < bottom_margin:
            next_page()

    def section_header(title):
        nonlocal y
        ensure_space(40)
        p.setFont("Helvetica-Bold", 14)
        p.drawString(50, y, f"■ {title}")
        y -= 20

    grouped = {
        "true_false": [], "mcq": [], "short_answer": [], "long_answer": []
    }
    for q in questions:
        grouped[q.question_type].append(q)

    # Title
    p.setFont("Helvetica-Bold", 18)
    p.drawCentredString(width / 2, y, f"{exam.name} - Answered Module")
    y -= 30

    # True/False
    if grouped["true_false"]:
        section_header("True/False Questions")
        for q in grouped["true_false"]:
            question_height = estimate_height(f"{q_number}. {q.text} [{q.marks} marks]", max_text_width) + 45
            ensure_space(question_height)
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            p.rect(width - 90, y + 5, 35, 15)
            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.2, 0.4, 0.9)
            p.drawString(width - 85, y + 7, q.correct_answer[:15])
            p.setFillColorRGB(0, 0, 0)
            y -= 35
            q_number += 1

    # MCQ
    if grouped["mcq"]:
        section_header("Multiple Choice Questions")
        for q in grouped["mcq"]:
            opt_line = "    ".join([f"{chr(65+i)}) {opt}" for i, opt in enumerate(q.get_mcq_options())])
            q_height = (
                estimate_height(f"{q_number}. {q.text} [{q.marks} marks]", max_text_width) +
                estimate_height(opt_line, max_text_width, font_size=11) +
                60
            )
            ensure_space(q_height)
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            y = draw_wrapped_text(p, 70, y, opt_line, max_text_width, font_size=11)
            y -= 10
            p.rect(width - 90, y + 5, 35, 15)
            p.setFont("Helvetica-Bold", 11)
            p.setFillColorRGB(0.2, 0.4, 0.9)
            p.drawString(width - 85, y + 7, q.correct_answer[:15])
            p.setFillColorRGB(0, 0, 0)
            y -= 30
            q_number += 1

   # Short Answer
    if grouped["short_answer"]:
        section_header("Short Answer Questions")
        for q in grouped["short_answer"]:
            text_height = estimate_height(f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            answer_height = estimate_height(q.correct_answer or "", width - 110, font_size=11)
            total_height = text_height + answer_height + 90
            ensure_space(total_height)
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            p.setDash(1, 2)
            p.rect(50, y - 60, width - 100, 60)
            p.setDash()
            y = draw_wrapped_text(p, 55, y - 20, q.correct_answer or "", width - 110,
                                font="Helvetica", font_size=11, color=(0.2, 0.4, 0.9))
            y -= 50  
            q_number += 1

    # Long Answer
    if grouped["long_answer"]:
        section_header("Long Answer Questions")
        for q in grouped["long_answer"]:
            text_height = estimate_height(f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            answer_height = estimate_height(q.correct_answer or "", width - 110, font_size=11)
            total_height = text_height + answer_height + 150
            ensure_space(total_height)
            y = draw_wrapped_text(p, 50, y, f"{q_number}. {q.text} [{q.marks} marks]", max_text_width)
            p.rect(50, y - 120, width - 100, 120)
            y = draw_wrapped_text(p, 55, y - 20, q.correct_answer or "", width - 110,
                                font="Helvetica", font_size=11, color=(0.2, 0.4, 0.9))
            y -= 80  
            q_number += 1

    draw_footer()
    p.save()
    buffer.seek(0)
    return FileResponse(buffer, as_attachment=True, filename=f"{exam.name}_AnsweredModule.pdf")

@login_required
@require_POST
def upload_student_paper(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized access."}, status=403)

    uploaded_files = request.FILES.getlist('student_papers')
    if not uploaded_files:
        return JsonResponse({"success": False, "error": "No files uploaded."})

    results = []
    from collections import defaultdict

    # Track names per student ID
    names_per_id = defaultdict(set)
    papers_by_id = defaultdict(list)

    for file in uploaded_files:
        paper = StudentPaper.objects.create(exam=exam, file=file)
        extracted_text = extract_text_from_pdf(paper.file.path)
        paper.text = extracted_text

        extracted_name, extracted_id = extract_name_and_id(extracted_text or "")
        if extracted_name and extracted_name.lower() != "empty":
            paper.manual_name = extracted_name

        if extracted_id:
            paper.manual_id = extracted_id
        
        if paper.manual_id and paper.manual_name:
            names_per_id[paper.manual_id].add(paper.manual_name.strip())
            papers_by_id[paper.manual_id].append(paper.id)

        # Try to match student
        parts = extracted_name.split()
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        try:
            matched_student = CustomUser.objects.get(
                first_name__icontains=first,
                last_name__icontains=last
            )
            paper.student = matched_student
        except CustomUser.DoesNotExist:
            pass

        paper.save()

        # ✅ AUTO-MERGE CHECK: Find others with same manual ID
        if paper.manual_id:
            matching_papers = StudentPaper.objects.filter(
                exam=exam,
                manual_id=paper.manual_id,
                merged_into__isnull=True
            ).exclude(id=paper.id)

            if matching_papers.exists():
                to_merge = list(matching_papers) + [paper]
                base_paper = to_merge[0]
                combined_text = "\n\n".join(p.text or "" for p in to_merge)

                for p in to_merge:
                    if p != base_paper:
                        p.is_merged = True
                        p.merged_into = base_paper
                        p.save()

                base_paper.text = combined_text
                base_paper.is_merged = True
                base_paper.merged_into = None
                base_paper.needs_regrading = True
                base_paper.save()

        results.append({"id": paper.id, "name": paper.manual_name})
    
    name_conflicts = {
        sid: list(names)
        for sid, names in names_per_id.items()
        if len(names) > 1
    }

    exam.update_status()
    return JsonResponse({
        "success": True,
        "total": len(results),
        "results": results,
        "conflicts": name_conflicts if name_conflicts else None,
        "paper_ids_by_id": dict(papers_by_id)
    })

@login_required
def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        messages.error(request, "You are not allowed to edit this exam.")
        return redirect('exams:detail', exam_id=exam.id)

    if request.method == "POST":
        exam.name = request.POST.get("exam_name")
        exam.total_marks = request.POST.get("total_marks")
        exam.duration_minutes = request.POST.get("exam_time")
        exam.save()

        # (Optional) Update questions here or handle with JS (more complex)

        messages.success(request, "✅ Exam updated successfully!")
        return redirect('exams:detail', exam_id=exam.id)

    courses = Course.objects.filter(instructor=request.user)
    questions = Question.objects.filter(exam=exam)
    return render(request, "exams/edit_exam.html", {
        "exam": exam,
        "courses": courses,
        "questions": questions,
    })

@require_POST
@login_required
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        messages.error(request, "⚠️ You don’t have permission to delete this exam.")
        return redirect("exams:list")

    exam.delete()
    messages.success(request, "🗑️ Exam deleted successfully.")
    return redirect("exams:list")


@login_required
def delete_paper(request, paper_id):
    try:
        paper = StudentPaper.objects.get(id=paper_id)
    except StudentPaper.DoesNotExist:
        messages.error(request, "⚠️ That paper doesn't exist or was already deleted.")
        return redirect("exams:list")

    exam = paper.exam
    paper.delete()
    exam.update_status()
    messages.success(request, "🗑️ Paper deleted successfully.")
    return redirect('exams:detail', exam_id=exam.id)


@require_POST
@login_required
def send_grades(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if not request.user.is_instructor:
        messages.error(request, "⚠️ Unauthorized.")
        return redirect("exams:detail", exam_id=exam.id)

    selected_ids = request.POST.getlist("student_ids")
    options = request.POST.getlist("send_options")
    selected_papers = StudentPaper.objects.filter(id__in=selected_ids, exam=exam)

    unmatched_ids = []
    sent_count = 0

    for paper in selected_papers:
        matched_student = paper.student

        if not matched_student:
            unmatched_ids.append(paper.id)
            print(f"❌ No matched student for paper ID {paper.id}")
            continue

        if matched_student not in exam.course.students.all():
            unmatched_ids.append(paper.id)
            print(f"❌ Student {matched_student.email} not enrolled in course.")
            continue

        print(f"\n📨 Sending to: {matched_student.email}")

        grade = Grade.objects.filter(studentpaper=paper).first()
        content = []

        # ✅ Log grade
        if "grades" in options and grade:
            score = grade.final_score()
            content.append(f"Score: {score}")
            print(f"✅ Grade: {score}")
        else:
            print("❌ Grade not included or missing")

        # ✅ Log AI feedback
        if "ai-feedback" in options and grade and grade.feedback:
            content.append(f"AI Feedback:\n{grade.feedback}")
            print("✅ AI Feedback included")
        else:
            print("❌ AI Feedback missing or not selected")

        # ✅ Log instructor feedback
        if "instructor-feedback" in options and paper.instructor_feedback:
            content.append(f"Instructor Feedback:\n{paper.instructor_feedback}")
            print("✅ Instructor Feedback included")
        else:
            print("❌ Instructor Feedback missing or not selected")

        attachments = []

        # ✅ Attach exam paper
        if "exam-paper" in options and paper.file:
            try:
                paper.file.open("rb")
                attachments.append((os.path.basename(paper.file.name), paper.file.read(), "application/pdf"))
                paper.file.close()
                print("✅ Exam Paper attached")
            except Exception as e:
                print(f"❌ Failed to attach Exam Paper: {e}")
        else:
            print("❌ Exam Paper not attached")

        attachments = []

        if "exam-paper" in options and paper.file:
            paper.file.open("rb")
            attachments.append((os.path.basename(paper.file.name), paper.file.read(), "application/pdf"))
            paper.file.close()

        sent_count += 1

    # Store unmatched for modal display
    request.session["unmatched_ids"] = unmatched_ids

    messages.success(request, f"✅ Grades sent to {sent_count} student(s).")
    return redirect("exams:detail", exam_id=exam.id)

@login_required
def calendar_events(request):
    user = request.user
    exams = Exam.objects.filter(course__instructor=user)  

    events = []
    for exam in exams:
        events.append({
            "title": f"{exam.name} (Exam)",
            "start": exam.created_at.strftime('%Y-%m-%d'),
            "url": f"/exams/{exam.id}/"  
        })

    return JsonResponse(events, safe=False)

@require_POST
@login_required
def override_score(request, exam_id, paper_id):
    paper = get_object_or_404(StudentPaper, id=paper_id)
    grade = Grade.objects.filter(studentpaper=paper, exam_id=exam_id).first()

    if request.user != paper.exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    override_value = request.POST.get("manual_override", "").strip()
    try:
        override_float = float(override_value)
        if override_float > paper.exam.total_marks:
            return JsonResponse({"success": False, "error": "Value exceeds total marks"})
    except ValueError:
        return JsonResponse({"success": False, "error": "Invalid value"})

    if grade:
        grade.manual_override = override_value
        grade.save()
        paper.exam.update_status()
        return JsonResponse({"success": True})
    return JsonResponse({"success": False, "error": "Grade not found"})

@csrf_exempt
@login_required
def edit_student_name(request, paper_id):
    if request.method == 'POST':
        paper = get_object_or_404(StudentPaper, id=paper_id)
        if request.user != paper.exam.instructor:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        new_name = request.POST.get("name", "").strip()
        if not new_name:
            return JsonResponse({"error": "Name cannot be empty"}, status=400)

        parts = new_name.split()
        first = parts[0]
        last = parts[-1] if len(parts) > 1 else ""
        matched_student = CustomUser.objects.filter(first_name__icontains=first, last_name__icontains=last).first()

        paper.student = matched_student
        paper.manual_name = new_name  
        paper.save()

        return JsonResponse({"success": True, "name": new_name})


@require_POST
@login_required
def resolve_flag(request, issue_id):
    issue = get_object_or_404(FlaggedIssue, id=issue_id)
    paper = issue.studentpaper

    if request.user != paper.exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    try:
        manual_score = float(request.POST.get("manual_score"))
        if manual_score > issue.question.marks:
            raise ValueError("Invalid score")

        issue.manual_score = manual_score
        issue.resolved = True
        issue.save()

        # Update Grade object if all issues are now resolved
        if not FlaggedIssue.objects.filter(studentpaper=paper, resolved=False).exists():
            total_score = sum(
                f.manual_score if f.manual_score is not None else 0
                for f in FlaggedIssue.objects.filter(studentpaper=paper)
            )
            grade = Grade.objects.filter(studentpaper=paper).first()
            if grade:
                grade.manual_override = total_score
                grade.save()

        paper.exam.update_status()
        messages.success(request, "✅ Flag resolved successfully.")
    except Exception as e:
        messages.error(request, f"⚠️ {str(e)}")

    return redirect("exams:detail", exam_id=paper.exam.id)

@csrf_exempt
@login_required
def edit_student_id(request, paper_id):
    if request.method == 'POST':
        paper = get_object_or_404(StudentPaper, id=paper_id)
        if request.user != paper.exam.instructor:
            return JsonResponse({"error": "Unauthorized"}, status=403)

        new_id = request.POST.get("student_id", "").strip()
        if not new_id:
            return JsonResponse({"error": "ID cannot be empty"}, status=400)

        if not new_id.isdigit():
            return JsonResponse({"error": "Student ID must be numeric."}, status=400)

        paper.manual_id = new_id
        paper.save()

        return JsonResponse({"success": True, "student_id": new_id})


@require_POST
@login_required
def save_instructor_feedback(request, paper_id):
    paper = get_object_or_404(StudentPaper, id=paper_id)

    if request.user != paper.exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    feedback = request.POST.get("feedback", "").strip()
    paper.instructor_feedback = feedback
    paper.save()

    return JsonResponse({"success": True})
