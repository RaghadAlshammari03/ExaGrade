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
            "class": "hidden peer",  # Hides the default radio button but keeps it functional
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

    email = forms.EmailField(
        widget=forms.EmailInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Enter your email",
        })
    )

    password1 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Enter your password",
        })
    )

    password2 = forms.CharField(
        widget=forms.PasswordInput(attrs={
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Confirm your password",
        })
    )

    class Meta:
        model = CustomUser
        fields = ["username", "email", "password1", "password2", "role"]

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("role"):
            raise forms.ValidationError("⚠️ Please select a role (Instructor or Student).")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
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
            "class": "w-full border border-gray-300 rounded-lg px-4 py-2 focus:border-[#1C304F] focus:outline-none",
            "placeholder": "Password"
        })
    )


class UserProfileForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ["username", "email", "phone_number", "bio", "profile_image"]
        widgets = {
            "username": forms.TextInput(attrs={
                "class": "border border-gray-300 rounded-lg px-4 py-2 w-full focus:border-[#1C304F] focus:outline-none",
                "placeholder": "Enter your username"
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
