from django.db import models
from users.models import CustomUser  # ✅ Import User model
from courses.models import Course  # ✅ Import Course model

# ✅ Electronic Exam Model
class ElectronicExam(models.Model):
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)  # ✅ Fixed relation
    total_marks = models.IntegerField(default=100)  # ✅ Ensure total_marks is always set
    duration_minutes = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)  # ✅ Added for exam status

    def __str__(self):
        return self.title

# ✅ Question Model
class Question(models.Model):
    exam = models.ForeignKey(ElectronicExam, on_delete=models.CASCADE, related_name="questions")
    text = models.TextField()
    question_type = models.CharField(
        max_length=20,
        choices=[
            ("MCQ", "Multiple Choice"),
            ("TF", "True/False"),
            ("SHORT", "Short Answer"),
            ("LONG", "Long Answer"),
        ],
    )
    ideal_answer = models.TextField(blank=True, null=True)  # ✅ For AI grading

    def __str__(self):
        return self.text

# ✅ Choice Model (for MCQs)
class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

# ✅ Student Response Model
class StudentResponse(models.Model):
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="responses")
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="responses")
    answer_text = models.TextField()
    is_correct = models.BooleanField(null=True, blank=True)  # ✅ AI grading field
    score = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"{self.student} - {self.question.text}"
