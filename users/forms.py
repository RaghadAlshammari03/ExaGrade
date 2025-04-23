from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import CustomUser


class SignupForm(UserCreationForm):
    ROLE_CHOICES = [
        ("instructor", "Instructor"),
        ("student", "Student"),
    ]

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            "class": "hidden peer"
        }),
        required=True,
        label="Register as",
    )

    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Enter your username",
        })
    )

    student_id = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Enter your student ID (students only)",
        })
    )

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Enter your email",
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "id": "id_password1",
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Enter your password",
        })
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "id": "id_password2",
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Confirm your password",
        })
    )

    class Meta:
        model = CustomUser
        fields = ["username", "email", "student_id", "password1", "password2", "role"]

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role")
        student_id = cleaned_data.get("student_id")

        if role == "student" and not student_id:
            raise forms.ValidationError("⚠️ Students must provide a Student ID.")
        if student_id and CustomUser.objects.filter(student_id=student_id).exists():
            raise forms.ValidationError("⚠️ A user with this Student ID already exists.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.student_id = self.cleaned_data.get("student_id")
        if self.cleaned_data["role"] == "instructor":
            user.is_instructor = True
            user.is_student = False
        else:
            user.is_student = True
            user.is_instructor = False
        if commit:
            user.save()
        return user


class LoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Username"
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "id": "id_password",
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Password"
        })
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["username", "email", "student_id", "phone_number", "bio", "profile_image"]
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none",
                "placeholder": "Enter your username"
            }),
            "student_id": forms.TextInput(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none",
                "placeholder": "Enter your student ID"
            }),
            "email": forms.EmailInput(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none",
                "placeholder": "Enter your email"
            }),
            "phone_number": forms.TextInput(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none",
                "placeholder": "Enter your phone number"
            }),
            "bio": forms.Textarea(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none",
                "rows": 3,
                "placeholder": "Tell us about yourself..."
            }),
            "profile_image": forms.ClearableFileInput(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none"
            }),
        }
