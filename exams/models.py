from django.db import models
from courses.models import Course
from users.models import CustomUser

class Exam(models.Model):
    STATUS_CHOICES = [
    ("done", "Complete"),
    ("progress", "In Progress"),
    ("pending", "Pending"),
    ("requires_attention", "Requires Attention"),
    ("new_papers_uploaded", "New Papers Uploaded"),
]
    
    EXAM_TYPE_CHOICES = [
        ("paper", "Paper Exam"),
        ("electronic", "Electronic Exam"),
    ]

    name = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="exams")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default="pending")
    was_done_once = models.BooleanField(default=False)
    exam_type = models.CharField(max_length=20, choices=EXAM_TYPE_CHOICES, default="paper")  
    instructor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="exams")
    student_paper = models.FileField(upload_to="exams/student_papers/", blank=True, null=True)
    solution_module = models.FileField(upload_to="exams/solution_modules/", blank=True, null=True)
    total_marks = models.PositiveIntegerField(default=0)
    duration_minutes = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.name

    def update_status(self):
        from exams.models import Grade, FlaggedIssue

        total_papers = self.student_papers.filter(is_merged=False).count()
        all_paper_ids = set(self.student_papers.values_list("id", flat=True))

        graded_paper_ids = set(
            Grade.objects.filter(
                exam=self,
                studentpaper__isnull=False
            ).exclude(grade__isnull=True).exclude(grade="").values_list("studentpaper_id", flat=True)
        )

        ungraded_paper_ids = all_paper_ids - graded_paper_ids

        print("total_papers:", total_papers)
        print("all_paper_ids:", all_paper_ids)
        print("graded_paper_ids:", graded_paper_ids)
        print("ungraded_paper_ids:", ungraded_paper_ids)
        print("was_done_once:", self.was_done_once)
        print("current status BEFORE:", self.status)

        previously_completed = self.was_done_once

        if FlaggedIssue.objects.filter(studentpaper__exam=self, resolved=False).exists():
            self.status = "requires_attention"
        elif total_papers == 0:
            self.status = "pending"
        elif len(graded_paper_ids) == 0:
            self.status = "pending"
        elif len(graded_paper_ids) == total_papers:
            self.status = "done"
            self.was_done_once = True
        elif self.was_done_once or len(graded_paper_ids) > 0: 
            if len(ungraded_paper_ids) > 0:
                self.status = "new_papers_uploaded"
        else:
            self.status = "progress"

        print("current status AFTER:", self.status)
        self.save()


EVAL_TYPE_CHOICES = [
    ('strict', 'Strict'),
    ('flexible', 'Flexible'),
    ('keywords', 'Keywords'),
    ('coding', 'Coding'),
    ('custom', 'Custom'),
]

class Question(models.Model):
    QUESTION_TYPES = [
        ("long_answer", "Long Answer"),
        ("short_answer", "Short Answer"),
        ("mcq", "Multiple Choice"),
        ("true_false", "True/False"),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPES)
    mcq_options = models.TextField(blank=True, null=True)  # Stores MCQ options as comma-separated values
    correct_answer = models.TextField(blank=True, null=True)
    marks = models.PositiveIntegerField(default=1)

    eval_type = models.CharField(max_length=50, choices=EVAL_TYPE_CHOICES, default='strict')
    custom_eval = models.TextField(blank=True, null=True)

    def get_mcq_options(self):
        return self.mcq_options.split(",") if self.mcq_options else []

    def __str__(self):
        return f"{self.exam.name} - {self.text[:50]}"


class StudentPaper(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="student_papers")
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="submitted_papers", blank=True, null=True)
    file = models.FileField(upload_to="exams/student_papers/")
    uploaded_at = models.DateTimeField(auto_now_add=True)
    text = models.TextField(blank=True, null=True)
    manual_name = models.CharField(max_length=255, blank=True, null=True) 
    manual_id = models.CharField(max_length=50, blank=True, null=True)
    manual_feedback = models.TextField(blank=True, null=True)
    instructor_feedback = models.TextField(blank=True, null=True)
    group_key = models.CharField(max_length=100, blank=True, null=True)  
    is_merged = models.BooleanField(default=False)
    needs_regrading = models.BooleanField(default=False)
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_papers")

    def __str__(self):
        return f"{self.student.username if self.student else 'Unassigned'} - {self.exam.name}"


class Grade(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, null=True, blank=True, related_name="grades_received")
    studentpaper = models.ForeignKey(StudentPaper, null=True, blank=True, on_delete=models.CASCADE)
    grade = models.CharField(max_length=10)
    feedback = models.TextField(blank=True, null=True)
    manual_override = models.FloatField(null=True, blank=True)
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="grades", null=True, blank=True)
    def final_score(self):
        return self.manual_override if self.manual_override else self.grade

    def __str__(self):
        return f"{self.student.username} - {self.exam.name} - {self.final_score()}"

class FlaggedIssue(models.Model):
    studentpaper = models.ForeignKey(StudentPaper, on_delete=models.CASCADE, related_name="flagged_issues")
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    flagged_text = models.TextField()  
    manual_score = models.FloatField(null=True, blank=True)
    resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Issue: {self.studentpaper} - {self.question}"

