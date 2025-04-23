from django import forms
from .models import ElectronicExam, Question

class ExamForm(forms.ModelForm):
    class Meta:
        model = ElectronicExam
        fields = ["course", "title"]

class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["exam", "text", "question_type", "ideal_answer"]
