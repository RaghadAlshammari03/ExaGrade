from django import forms
from .models import Exam, Question, Course
from django.forms import modelformset_factory, inlineformset_factory

class ExamForm(forms.ModelForm):
    class Meta:
        model = Exam
        fields = ["name", "solution_module"]
        widgets = {
            "name": forms.TextInput(attrs={
                "class": "border rounded-lg px-4 py-2 w-full",
                "placeholder": "Enter exam name",
                "required": True
            }),
            "solution_module": forms.ClearableFileInput(attrs={
                "class": "border rounded-lg px-4 py-2 w-full"
            })
        }

    def clean_name(self):
        name = self.cleaned_data.get("name")
        if not name:
            raise forms.ValidationError("⚠️ Exam name is required.")
        return name

    def clean_solution_module(self):
        solution_module = self.cleaned_data.get("solution_module")
        if solution_module and not solution_module.name.endswith('.pdf'):
            raise forms.ValidationError("❌ The solution module must be a PDF file.")
        return solution_module

    def clean(self):
        cleaned_data = super().clean()
        name = cleaned_data.get("name")
        if not name:
            self.add_error("name", "Exam name is required.")
        return cleaned_data


class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ["text", "question_type", "mcq_options", "correct_answer"]
        widgets = {
            "text": forms.Textarea(attrs={
                "class": "border rounded-lg px-4 py-2 w-full",
                "placeholder": "Enter question text",
                "rows": 3
            }),
            "question_type": forms.HiddenInput(attrs={
                "class": "question-type-input"
            }),
            "mcq_options": forms.TextInput(attrs={
                "class": "border rounded-lg px-4 py-2 w-full mcq-field",
                "placeholder": "Enter MCQ options (comma-separated)",
                "style": "display: none;"
            }),
            "correct_answer": forms.TextInput(attrs={
                "class": "border rounded-lg px-4 py-2 w-full",
                "placeholder": "Enter the correct answer"
            })
        }

    def clean_mcq_options(self):
        mcq_options = self.cleaned_data.get("mcq_options")
        question_type = self.cleaned_data.get("question_type")
        if question_type == "mcq" and not mcq_options:
            raise forms.ValidationError("❌ MCQ questions must have answer options.")
        return mcq_options

    def clean_correct_answer(self):
        correct_answer = self.cleaned_data.get("correct_answer")
        question_type = self.cleaned_data.get("question_type")
        if question_type == "mcq" and not correct_answer:
            raise forms.ValidationError("❌ MCQ questions must have a correct answer.")
        return correct_answer


# Create the Question Formset
QuestionFormSet = inlineformset_factory(
    Exam,
    Question,
    form=QuestionForm,
    extra=0,
    can_delete=True,
    min_num=1,  # Require at least one question
    validate_min=True,
)
