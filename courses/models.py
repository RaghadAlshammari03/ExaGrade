import random
import string
from django.db import models
from users.models import CustomUser

class Course(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, null=True)
    instructor = models.ForeignKey(CustomUser, on_delete=models.CASCADE, related_name="courses")
    students = models.ManyToManyField(CustomUser, related_name="enrolled_courses", blank=True)
    course_code = models.CharField(max_length=6, unique=True, blank=True)  # Unique 6-digit code

    def save(self, *args, **kwargs):
        if not self.course_code:  # Generate a unique 6-digit code when a course is created
            self.course_code = ''.join(random.choices(string.digits, k=6))
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.course_code})"
