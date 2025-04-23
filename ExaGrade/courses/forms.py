from django import forms
from .models import Course

class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["name", "description"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "border rounded-lg px-4 py-2 w-full"}),
            "description": forms.Textarea(attrs={"class": "border rounded-lg px-4 py-2 w-full", "rows": 3}),
        }

