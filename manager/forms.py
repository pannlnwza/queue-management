from django import forms
from .models import Queue, UserProfile  # Assuming Queue model is in the same app
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class QueueForm(forms.ModelForm):
    """
    Form for creating or updating a Queue instance.

    This form allows users to input the necessary details for a queue,
    including its name and description.
    """

    class Meta:
        model = Queue
        fields = ['name', 'logo', 'description', 'category', 'latitude',
                  'longitude']
        labels = {
            'logo': 'Logo (Optional)'
        }
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'input input-bordered w-full max-w-xs m-2',
                       'placeholder': 'Enter Queue Name (Max Length: 50)'}),
            'description': forms.Textarea(
                attrs={'class': 'textarea textarea-bordered w-full m-2',
                       'placeholder': 'Enter Description (Max Length: 60)',
                       'rows': 4}),
            'category': forms.Select(
                attrs={'class': 'select select-bordered w-full max-w-xs m-2'}),
            'logo': forms.ClearableFileInput(
                attrs={'class': 'file-input w-full max-w-xs m-2',
                       'accept': 'image/*'}),

        }

class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super(CustomUserCreationForm, self).save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class EditProfileForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    phone = forms.CharField(max_length=10, required=False)
    image = forms.ImageField(required=False)

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'phone', 'image', 'first_name', 'last_name']
