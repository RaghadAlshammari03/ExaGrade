from .models import Grade

def get_grading_stage_text(exam):
    all_paper_ids = set(exam.student_papers.values_list("id", flat=True))
    graded_paper_ids = set(Grade.objects.filter(exam=exam).values_list("studentpaper_id", flat=True))

    if not graded_paper_ids:
        return "Grade Exam"
    elif all_paper_ids - graded_paper_ids:
        return "Grade New Papers"
    return "Regrade All"
