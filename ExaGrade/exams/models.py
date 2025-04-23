from django.db import models
from django.apps import apps  # ✅ Fix circular import issues
from users.models import CustomUser  # ✅ Direct import is safe

class Exam(models.Model):
    STATUS_CHOICES = [
        ("done", "Done"),
        ("progress", "Progress"),
        ("pending", "Pending"),
        ("requires_attention", "Requires Attention"),
    ]

    name = models.CharField(max_length=255)
    course = models.ForeignKey("courses.Course", on_delete=models.CASCADE, related_name="exams")
    created_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")
    instructor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="exams")

    solution_module = models.FileField(upload_to="exams/solution_modules/", blank=True, null=True)
    student_paper = models.FileField(upload_to="exams/student_papers/", blank=True, null=True)
    pdf_file = models.FileField(upload_to="exams/pdfs/", blank=True, null=True)

    def __str__(self):
        return self.name

    def get_questions(self):
        """Dynamically load related questions to avoid circular imports."""
        Question = apps.get_model("exams", "Question")
        return Question.objects.filter(exam=self)

    def get_grades(self):
        """Dynamically load related grades to avoid circular imports."""
        Grade = apps.get_model("exams", "Grade")
        return Grade.objects.filter(exam=self)

class Question(models.Model):
    QUESTION_TYPES = [
        ("TF", "True/False"),
        ("MCQ", "Multiple Choice"),
        ("SA", "Short Answer"),
        ("LA", "Long Answer"),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(max_length=10, choices=QUESTION_TYPES)

    def __str__(self):
        return f"{self.exam.name} - {self.text}"

class Grade(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="grades")
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="grades")
    score = models.FloatField()
    feedback = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.student.username} - {self.exam.name} - {self.score}"
