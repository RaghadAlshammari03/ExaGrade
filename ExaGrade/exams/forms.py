from django import forms
from .models import Exam, Question

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["name", "solution_module", "student_paper"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "border rounded-lg px-4 py-2 w-full", "required": True}),
            "solution_module": forms.ClearableFileInput(attrs={"class": "border rounded-lg px-4 py-2 w-full"}),
            "student_paper": forms.ClearableFileInput(attrs={"class": "border rounded-lg px-4 py-2 w-full"}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("name"):
            self.add_error("name", "Exam name is required.")
        return cleaned_data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "question_type"]
        labels = {
            "text": "Enter Your Question",
            "question_type": "Select Question Type",
        }
        widgets = {
            "question_type": forms.Select(choices=Question.QUESTION_TYPES),
        }
