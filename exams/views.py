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
from utils.grading import grade_answer, parse_score_and_feedback
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
from collections import defaultdict
from datetime import datetime
from .utils import generate_answered_pdf_from_data, generate_exam_pdf_from_data
from django.http import QueryDict


@login_required
def exam_list_view(request):
    if request.user.is_instructor:
        exams = Exam.objects.filter(course__in=request.user.courses.all())
    else:
        exams = Exam.objects.filter(course__in=request.user.enrolled_courses.all())
    return render(request, "exams/exam_list.html", {"exams": exams})

@login_required
def exam_detail_view(request, exam_id):
    from collections import defaultdict
    import os

    exam = get_object_or_404(Exam, id=exam_id)

    if request.user.is_instructor:
        context = {}
        student_papers = StudentPaper.objects.filter(exam=exam).select_related('student')
        enrolled_students = set(exam.course.students.all())
        grades = Grade.objects.filter(exam=exam)
        graded_paper_ids = set(grades.values_list("studentpaper_id", flat=True))
        has_graded_papers = grades.exists()

        # Step 1: Extract text and name/id for all papers individually
        for paper in student_papers:
            if not paper.text and paper.file and os.path.exists(paper.file.path):
                paper.text = extract_text_from_pdf(paper.file.path)
            if paper.text:
                extracted_name, extracted_id = extract_name_and_id(paper.text)
                if not paper.manual_name and extracted_name and extracted_name.lower() != "empty":
                    paper.manual_name = extracted_name
                if not paper.manual_id and extracted_id:
                    paper.manual_id = extracted_id
            paper.save()

        # Step 2: Group by manual_id (after cleaning)
        grouped = defaultdict(list)
        for paper in student_papers:
            base_paper = paper.merged_into if paper.merged_into else paper
            key = base_paper.id
            grouped[key].append(paper)

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

        paper_data = []
        unmatched_ids = []

        for group_id, papers in grouped.items():
            base_paper = papers[0]

            matched_student = base_paper.student
            if not matched_student and base_paper.manual_id:
                try:
                    matched_student = CustomUser.objects.get(student_id=base_paper.manual_id)
                    base_paper.student = matched_student
                    base_paper.save()
                except CustomUser.DoesNotExist:
                    matched_student = None

            is_enrolled_and_matched = matched_student in enrolled_students
            if not is_enrolled_and_matched:
                unmatched_ids.extend([p.id for p in papers])

            grade = Grade.objects.filter(studentpaper__in=papers).first()
            display_name = base_paper.manual_name.strip() if base_paper.manual_name else (
                matched_student.get_full_name() if matched_student else "Empty"
            )

            paper_entries = []
            extract_entries = []

            if len(papers) > 1:
                combined_text = "\n\n".join(p.text or "" for p in papers)
                extract_entries.append({
                    "label": "All Papers",
                    "text": combined_text,
                    "id": f"all_{base_paper.id}"
                })

            for idx, p in enumerate(papers):
                paper_entries.append({
                    "label": f"Paper {idx + 1}",
                    "url": p.file.url,
                    "id": p.id
                })
                extract_entries.append({
                    "label": f"Paper {idx + 1}",
                    "text": p.text or "",
                    "id": p.id
                })

            paper_data.append({
                "id": base_paper.id,
                "student_name": display_name,
                "student_id": base_paper.manual_id or "—",
                "grade": grade.grade if grade else "not graded yet",
                "manual_override": grade.manual_override if grade and grade.manual_override else None,
                "feedback": grade.feedback if grade else None,
                "instructor_feedback": base_paper.instructor_feedback or "",
                "is_enrolled_and_matched": is_enrolled_and_matched,
                "badges": list(filter(None, [
                    {"text": "Ungraded", "style": "bg-yellow-100 text-yellow-800"} if base_paper.id not in graded_paper_ids else None,
                    {"text": "Name Missing", "style": "bg-red-100 text-red-700"} if not base_paper.manual_name and not matched_student else None,
                    {"text": "ID Missing", "style": "bg-orange-100 text-orange-700"} if not base_paper.manual_id else None,
                    {"text": "⚠️ Review Needed", "style": "bg-red-100 text-red-700"} if any(p.flagged_issues.filter(resolved=False).exists() for p in papers) else None,
                    {"text": "Not Enrolled", "style": "bg-gray-100 text-gray-600 italic"} if not is_enrolled_and_matched else None,
                    {"text": "Enrolled", "style": "bg-green-100 text-green-700"} if is_enrolled_and_matched else None,
                    {"text": "Merged", "style": "bg-purple-100 text-purple-800"} if len(papers) > 1 else None,
                ])),
                "merged_files": paper_entries,
                "merged_extracts": extract_entries,
                "graded_questions": split_feedback_into_questions(grade.feedback) if grade and grade.feedback else [],
                "paper_ids": [p.id for p in papers],
                "is_merged": len(papers) > 1,
            })

        exam.update_status()

        context.update({
            "exam": exam,
            "paper_data": paper_data,
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
            "student_papers": student_papers,
        })

        request.session["unmatched_ids"] = unmatched_ids

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
    
    fields = [
        ("instructor_name", "Instructor Name"),
        ("course_name", "Course Name"),
        ("exam_name", "Exam Name"),
        ("student_name", "Student Name"),
        ("student_id", "Student ID"),
        ("paper_number", "Student Number")
    ]

    header_fields = [
        "instructor_name", "course_name", "exam_name",
        "student_name", "student_id", "paper_number"
    ]

    expected_lines = ["3", "5", "7", "10", "12", "15", "20"]

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
        total_marks = request.POST.get("total_marks") or 0
        total_marks = int(total_marks)
        print("[DEBUG] exam_name:", exam_name)
        print("[DEBUG] course_id:", course_id)
        print("[DEBUG] total_marks:", total_marks)


        header_fields_selected = request.POST.getlist("header_fields")
        if (
            ("exam_name" in header_fields_selected and not exam_name)
            or ("course_name" in header_fields_selected and not course_id)
        ):
            messages.error(request, "⚠️ Please fill in all required fields.")
            return render(request, "exams/add_exam.html", {
                "courses": Course.objects.filter(instructor=request.user),
                "exam": exam_to_edit,
                "questions_by_type": questions_by_type,
                "fields": fields,
                "expected_lines": expected_lines,
                "header_fields": header_fields_selected,
                "form_data": request.POST,
            })

        try:
            course = Course.objects.get(id=course_id, instructor=request.user)
        except Course.DoesNotExist:
            messages.error(request, "❌ Invalid course.")
            return redirect("exams:add")

        if exam_to_edit:
            exam = exam_to_edit
            exam.name = exam_name
            exam.course = course
            exam.total_marks = total_marks
            exam.save()
            Question.objects.filter(exam=exam).delete()
        else:
            exam = Exam.objects.create(
                name=exam_name,
                course=course,
                instructor=request.user,
                total_marks=total_marks,
            )

        # True/False
        tf_questions = request.POST.getlist('tf_questions[]')
        tf_answers = request.POST.getlist('tf_answers[]')
        tf_marks = request.POST.getlist('tf_marks[]')
        print("[DEBUG] tf_questions:", tf_questions)
        print("[DEBUG] tf_answers:", tf_answers)
        print("[DEBUG] tf_marks:", tf_marks)

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
        print("[DEBUG] mcq_questions:", mcq_questions)
        print("[DEBUG] mcq_options:", opt1, opt2, opt3, opt4)
        print("[DEBUG] mcq_answers:", answers)
        print("[DEBUG] mcq_marks:", mcq_marks)

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
        print("[DEBUG] short_questions:", short_questions)
        print("[DEBUG] short_answers:", short_answers)
        print("[DEBUG] short_marks:", short_marks)
        print("[DEBUG] short_eval_types:", short_eval_types)

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
        print("[DEBUG] long_questions:", long_questions)
        print("[DEBUG] long_answers:", long_answers)
        print("[DEBUG] long_marks:", long_marks)
        print("[DEBUG] long_eval_types:", long_eval_types)

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
        request.session[f"exam_form_data_{exam.id}"] = dict(request.POST)
        return redirect("exams:list")

    courses = Course.objects.filter(instructor=request.user)

    return render(request, "exams/add_exam.html", {
        "courses": courses,
        "exam": exam_to_edit,
        "questions_by_type": questions_by_type,
        "fields": fields,
        "expected_lines": expected_lines,
        "header_fields": header_fields,
    })

@require_POST
@login_required
def grade_exam(request, exam_id):
    from utils.parser import group_papers_by_id
    from utils.grading import grade_answer, parse_score_and_feedback
    from exams.models import FlaggedIssue
    from datetime import datetime

    start_time = datetime.now()

    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)
        messages.error(request, "⚠️ You are not authorized to grade this exam.")
        return redirect("exams:detail", exam_id=exam.id)

    mode = request.POST.get("mode", "").lower()
    grouped, _ = group_papers_by_id(exam)
    questions = exam.questions.all()
    graded_results = []

    for group_key, papers in grouped.items():
        combined_text = "\n\n".join([p.text or "" for p in papers])
        student_id = papers[0].manual_id or ""
        student = CustomUser.objects.filter(student_id=student_id).first() if student_id else None

        already_graded = Grade.objects.filter(exam=exam, studentpaper__in=papers).exists()
        needs_regrading = any(p.needs_regrading for p in papers)

        if mode == "new" and not needs_regrading:
            continue
        elif mode == "regrade":
            Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()
            FlaggedIssue.objects.filter(studentpaper__in=papers).delete()
        elif already_graded and not needs_regrading:
            continue

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
    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    print(f"✅ Graded {len(graded_results)} students in {elapsed:.2f} seconds.")

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
    from utils.grading import grade_answer, parse_score_and_feedback

    exam = get_object_or_404(Exam, id=exam_id)
    base_paper = get_object_or_404(StudentPaper, id=paper_id, exam=exam)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    papers = [base_paper]
    if base_paper.is_merged:
        papers += list(base_paper.merged_papers.all())

    combined_text = "\n\n".join([p.text or "" for p in papers])

    student_id = base_paper.manual_id or ""
    student = CustomUser.objects.filter(student_id=student_id).first() if student_id else None

    Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()
    FlaggedIssue.objects.filter(studentpaper__in=papers).delete()

    total_score = 0
    feedback_parts = []
    q_number = 1
    questions = exam.questions.all()

    for q in questions:
        result = grade_answer(
            q.text, combined_text, q.correct_answer, q.marks,
            eval_type=q.eval_type or "strict",
            custom_note=q.custom_eval or "",
            question_type=q.question_type
        )
        score, feedback, needs_attention = parse_score_and_feedback(result, q.marks, q_number)

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
        q_number += 1

    Grade.objects.create(
        student=student,
        studentpaper=base_paper,
        exam=exam,
        grade=str(total_score),
        feedback="<br><br>".join(feedback_parts)
    )

    for p in papers:
        p.needs_regrading = False
        p.save()

    exam.update_status()

    return JsonResponse({"success": True})

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

    base_paper = papers.order_by('id').first()

    for paper in papers:
        if paper != base_paper:
            paper.is_merged = True
            paper.merged_into = base_paper  
            paper.needs_regrading = True
            paper.save()

    base_paper.is_merged = True
    base_paper.merged_into = None  
    base_paper.needs_regrading = True
    base_paper.save()

    Grade.objects.filter(exam=exam, studentpaper__in=papers).delete()

    return JsonResponse({"success": True, "message": f"Merged {papers.count()} papers for ID: {student_id}"})


@require_POST
@login_required
def merge_papers_by_id(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        return JsonResponse({"error": "Unauthorized"}, status=403)

    paper_ids = request.POST.getlist('paper_ids')
    if len(paper_ids) < 2:
        return JsonResponse({"error": "Select at least 2 papers to merge."}, status=400)

    papers = StudentPaper.objects.filter(id__in=paper_ids, exam=exam)

    manual_ids = set(p.manual_id for p in papers if p.manual_id)
    if len(manual_ids) != 1:
        return JsonResponse({"error": "Cannot merge papers with different Student IDs."}, status=400)

    base_paper = papers.order_by('id').first()

    base_paper.is_merged = True
    base_paper.merged_into = None
    base_paper.needs_regrading = True
    base_paper.save()

    for paper in papers:
        if paper != base_paper:
            paper.is_merged = True
            paper.merged_into = base_paper
            paper.needs_regrading = True
            paper.save()

    Grade.objects.filter(studentpaper__in=papers, exam=exam).delete()

    print(f"[✅] Successfully merged {len(papers)} papers into base_paper ID {base_paper.id} (student_id={base_paper.manual_id})")

    return JsonResponse({"success": True, "message": f"Merged {len(papers)} papers successfully."})


@require_POST
@login_required
def merge_papers(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    paper_ids = request.POST.getlist('paper_ids')
    if len(paper_ids) < 2:
        return JsonResponse({"success": False, "error": "Select at least 2 papers to merge."}, status=400)

    papers = StudentPaper.objects.filter(id__in=paper_ids, exam=exam)

    ids = set(p.manual_id for p in papers)
    names = set((p.manual_name or "").strip().lower() for p in papers)
    raw_names = set((p.manual_name or "") for p in papers)

    if "-" in ids or "" in ids or None in ids:
        return JsonResponse({
            "success": False,
            "error": "Cannot merge: One or more papers are missing a student ID."
        }, status=200)

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

    for p in papers:
        if p != base_paper:
            p.is_merged = True
            p.merged_into = base_paper
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

@require_POST
@login_required
def unmerge_papers(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body)
        paper_id = data.get('paper_id')
    except Exception:
        return JsonResponse({"success": False, "error": "Invalid JSON"})

    if not paper_id:
        return JsonResponse({"success": False, "error": "Paper ID missing."})

    merged_paper = get_object_or_404(StudentPaper, id=paper_id, exam=exam)

    if not merged_paper.is_merged:
        return JsonResponse({"success": False, "error": "This paper is not a merged paper."})

    if merged_paper.merged_files:
        for file_obj in merged_paper.merged_files.all():
            StudentPaper.objects.create(
                exam=exam,
                file=file_obj.file,
                manual_name=merged_paper.manual_name,
                manual_id=merged_paper.manual_id,
                is_merged=False,
                needs_regrading=True,
            )

    merged_paper.delete()

    exam.update_status()

    return JsonResponse({"success": True, "message": "Successfully unmerged."})

@require_POST
@login_required
def unmerge_papers_by_id(request, exam_id):
    import json
    from django.http import JsonResponse
    from django.shortcuts import get_object_or_404
    from .models import StudentPaper

    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        print("[❌] Unauthorized access attempt to unmerge.")
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    try:
        data = json.loads(request.body)
        student_id = data.get('student_id')
    except Exception as e:
        print(f"[❌] JSON parsing error: {e}")
        return JsonResponse({"success": False, "error": "Invalid JSON"}, status=400)

    if not student_id:
        print("[❌] No student ID provided.")
        return JsonResponse({"success": False, "error": "Student ID missing"}, status=400)

    print(f"[🔎] Trying to unmerge papers for student_id={student_id}")

    # Step 1: Try to find the parent merged paper
    parent_paper = StudentPaper.objects.filter(
        exam=exam,
        manual_id=student_id,
        merged_into=None
    ).first()

    if not parent_paper:
        print("[⚠️] No direct parent found. Trying fallback (any is_merged=True paper)")
        parent_paper = StudentPaper.objects.filter(
            exam=exam,
            manual_id=student_id,
            is_merged=True
        ).first()

    if not parent_paper:
        print(f"[❌] No merged paper found with student_id={student_id}")
        return JsonResponse({"success": False, "error": "No merged paper found for this student ID"}, status=404)

    print(f"[✅] Found parent paper: id={parent_paper.id}, manual_id={parent_paper.manual_id}, is_merged={parent_paper.is_merged}")

    # Step 2: Find all children papers
    merged_children = StudentPaper.objects.filter(merged_into=parent_paper)

    print(f"[📄] Found {merged_children.count()} merged children linked to parent paper.")

    # Step 3: Unmerge children
    if merged_children.exists():
        for child in merged_children:
            print(f"[➡️] Unmerging child paper id={child.id}")
            child.is_merged = False
            child.merged_into = None
            child.manual_id = None  # Clear manual_id (optional depending on design)
            child.needs_regrading = True
            child.save()
            print(f"[✅] Unmerged child id={child.id} successfully.")
    else:
        print("[ℹ️] No merged children. Only parent paper will be unmerged.")

    # Step 4: Unmerge parent paper itself
    parent_paper.is_merged = False
    parent_paper.merged_into = None
    parent_paper.needs_regrading = True
    parent_paper.save()
    print(f"[✅] Parent paper id={parent_paper.id} unmerged successfully.")

    # Step 5: Update exam status
    exam.update_status()
    print("[🔃] Exam status updated.")

    return JsonResponse({"success": True, "message": "Successfully unmerged."})


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
    for p in papers:
        if p != base_paper:
            p.is_merged = True
            p.merged_into = base_paper
            p.save()

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

@login_required
def generate_exam_pdf(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    post_data = request.session.get(f"exam_form_data_{exam_id}")
    if not post_data:
        messages.error(request, "⚠️ No saved form data found. Please re-save the exam to generate the PDF.")
        return redirect("exams:edit_exam", exam_id=exam.id)

    request.POST = QueryDict('', mutable=True)
    for key, value in post_data.items():
        if isinstance(value, list):
            for v in value:
                request.POST.update({key: v})
        else:
            request.POST[key] = value

    return generate_exam_pdf_from_data(request)

@login_required
def generate_answered_pdf(request, exam_id):

    exam = get_object_or_404(Exam, id=exam_id)

    post_data = request.session.get(f"exam_form_data_{exam_id}")
    if not post_data:
        messages.error(request, "⚠️ No saved form data found. Please re-save the exam to generate the PDF.")
        return redirect("exams:edit_exam", exam_id=exam.id)

    request.POST = QueryDict('', mutable=True)
    for key, value in post_data.items():
        if isinstance(value, list):
            for v in value:
                request.POST.update({key: v})
        else:
            request.POST[key] = value

    return generate_answered_pdf_from_data(request)

@csrf_exempt
def preview_exam_pdf(request):
    from .utils import generate_exam_pdf_from_data
    return generate_exam_pdf_from_data(request)

@csrf_exempt
def preview_answered_pdf(request):
    from .utils import generate_answered_pdf_from_data
    return generate_answered_pdf_from_data(request)

@login_required
@require_POST
def upload_student_paper(request, exam_id):
    start_time = datetime.now()

    exam = get_object_or_404(Exam, id=exam_id)
    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized access."}, status=403)

    uploaded_files = request.FILES.getlist('student_papers')
    if not uploaded_files:
        return JsonResponse({"success": False, "error": "No files uploaded."})

    results = []
    names_per_id = defaultdict(set)
    papers_by_id = defaultdict(list)

    for file in uploaded_files:
        paper = StudentPaper.objects.create(exam=exam, file=file)
        extracted_text = extract_text_from_pdf(paper.file.path)
        paper.text = extracted_text

        extracted_name, extracted_id = extract_name_and_id(extracted_text or "")
        if extracted_name and extracted_name.lower() != "empty":
            paper.manual_name = extracted_name.strip()

        if extracted_id:
            paper.manual_id = extracted_id.strip()

        if paper.manual_id and paper.manual_name:
            names_per_id[paper.manual_id].add(paper.manual_name)
            papers_by_id[paper.manual_id].append(paper.id)

        if paper.manual_name:
            parts = paper.manual_name.split()
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

    student_papers = StudentPaper.objects.filter(exam=exam)
    grouped = defaultdict(list)
    for paper in student_papers:
        if paper.manual_id:
            grouped[paper.manual_id].append(paper)

    name_conflicts = {}

    for student_id, papers in grouped.items():
        if len(papers) >= 2:
            names = set((p.manual_name or "").strip().lower() for p in papers)

            if len(names) > 1:
                name_conflicts[student_id] = list(names)
            else:
                base_paper = papers[0]
                for p in papers:
                    if p != base_paper:
                        p.is_merged = True
                        p.merged_into = base_paper
                        p.save()
                base_paper.is_merged = True
                base_paper.needs_regrading = True
                base_paper.save()

    exam.update_status()

    end_time = datetime.now()
    elapsed = (end_time - start_time).total_seconds()
    print(f"🧠 Uploaded {len(uploaded_files)} paper(s) in {elapsed:.2f} seconds.")

    return JsonResponse({
        "success": True,
        "total": len(uploaded_files),
        "results": [{"id": p.id, "name": p.manual_name} for p in student_papers],
        "conflicts": name_conflicts if name_conflicts else None,
        "paper_ids_by_id": {k: [str(id) for id in v] for k, v in papers_by_id.items()}
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
        exam.save()

        messages.success(request, "✅ Exam updated successfully!")
        return redirect('exams:detail', exam_id=exam.id)

    courses = Course.objects.filter(instructor=request.user)
    questions = Question.objects.filter(exam=exam)
    return render(request, "exams/add_exam.html", {
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

        if "grades" in options and grade:
            score = grade.final_score()
            content.append(f"Score: {score}")
            print(f"✅ Grade: {score}")
        else:
            print("❌ Grade not included or missing")

        if "ai-feedback" in options and grade and grade.feedback:
            content.append(f"AI Feedback:\n{grade.feedback}")
            print("✅ AI Feedback included")
        else:
            print("❌ AI Feedback missing or not selected")

        if "instructor-feedback" in options and paper.instructor_feedback:
            content.append(f"Instructor Feedback:\n{paper.instructor_feedback}")
            print("✅ Instructor Feedback included")
        else:
            print("❌ Instructor Feedback missing or not selected")

        attachments = []

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

@require_POST
@login_required
def delete_all_papers(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)

    if request.user != exam.instructor:
        return JsonResponse({"success": False, "error": "Unauthorized"}, status=403)

    StudentPaper.objects.filter(exam=exam).delete()
    Grade.objects.filter(exam=exam).delete()
    FlaggedIssue.objects.filter(studentpaper__exam=exam).delete()

    exam.update_status()

    print("🗑️ All student papers deleted for exam:", exam.name)
    return JsonResponse({"success": True, "message": "All student papers deleted."})
