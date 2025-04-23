from django.db import models
from users.models import CustomUser  
from courses.models import Course  


EVAL_TYPE_CHOICES = [
    ('strict', 'Strict'),
    ('flexible', 'Flexible'),
    ('keywords', 'Keywords'),
    ('coding', 'Coding'),
    ('custom', 'Custom'),
]

class ElectronicExam(models.Model):
    title = models.CharField(max_length=255)
    course = models.ForeignKey(Course, on_delete=models.CASCADE)  
    total_marks = models.IntegerField(default=100)  
    duration_minutes = models.IntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=False)  
    created_at = models.DateTimeField(auto_now_add=True)
    can_navigate = models.BooleanField(default=True, help_text="Allow students to go back and forth between questions")
    status = models.CharField(
    max_length=30,
    choices=[
        ("done", "Complete"),
        ("progress", "In Progress"),
        ("pending", "Pending"),
        ("requires_attention", "Requires Attention"),
    ],
    default="pending"
)
    was_done_once = models.BooleanField(default=False)
    grades_released = models.BooleanField(default=False) 

    def update_status(self):
        from .models import StudentResponse

        responses = StudentResponse.objects.filter(question__exam=self)
        total_responses = responses.count()
        graded_responses = responses.exclude(score__isnull=True).count()

        print("🧪 total_responses:", total_responses)
        print("🧪 graded_responses:", graded_responses)

        if total_responses == 0 or graded_responses == 0:
            self.status = "pending"
        elif graded_responses == total_responses:
            self.status = "done"  
        else:
            self.status = "progress"

        print("🧪 current status:", self.status)
        self.save()

    def __str__(self):
        return self.title

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
    ideal_answer = models.TextField(blank=True, null=True)
    marks = models.PositiveIntegerField(default=1)
    
    
    eval_type = models.CharField(
        max_length=50,
        choices=EVAL_TYPE_CHOICES,
        default='strict'
    )
    custom_eval = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.text

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text

class StudentResponse(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name="responses")
    student = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="responses")
    exam = models.ForeignKey(ElectronicExam, on_delete=models.CASCADE, related_name="student_responses")
    answer_text = models.TextField()
    is_correct = models.BooleanField(null=True, blank=True)  
    score = models.FloatField(null=True, blank=True)
    requires_attention = models.BooleanField(default=False)
    manual_name = models.CharField(max_length=255, blank=True, null=True)
    feedback = models.TextField(null=True, blank=True)
    manual_feedback = models.TextField(blank=True, null=True)
    is_score_override = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.student} - {self.question.text}"