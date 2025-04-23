from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class CustomUser(AbstractUser):
    is_instructor = models.BooleanField(default=False)
    is_student = models.BooleanField(default=False)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    student_id = models.CharField(max_length=20, blank=True, null=True, unique=True)
    bio = models.TextField(blank=True, null=True)
    profile_image = models.ImageField(
        upload_to="profiles/",
        default="profiles/profile-default.png",
        null=True,
        blank=True
    )
    username = models.CharField(
        max_length=150,
        unique=True,
        validators=[
            RegexValidator(
                regex=r'^[\w.@+\- ]+$',
                message="Username may contain letters, numbers, spaces, and @/./+/-/_ characters."
            )
        ],
        help_text="Required. 150 characters or fewer. Letters, digits, spaces and @/./+/-/_ only.",
    )


def save(self, *args, **kwargs):
        if not self.profile_image:  
            self.profile_image = "profiles/profile-default.png"
        super().save(*args, **kwargs)

def __str__(self):
    return self.username