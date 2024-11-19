from django import forms
from .models import Queue, UserProfile, Resource, Doctor
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
        fields = ['name', 'logo', 'description', 'category']
        labels = {
            'logo': 'Logo (Optional)'
        }
        widgets = {
            'name': forms.TextInput(
                attrs={'class': 'input input-bordered w-full max-w-xs m-4',
                       'placeholder': 'Enter Queue Name (Max Length: 50)'}),
            'description': forms.Textarea(
                attrs={'class': 'textarea textarea-bordered w-full m-4',
                       'placeholder': 'Enter Description (Max Length: 60)',
                       'rows': 4}),
            'category': forms.Select(
                attrs={'class': 'select select-bordered w-full max-w-xs m-4'}),
            'logo': forms.ClearableFileInput(
                attrs={'class': 'file-input file-input-bordered w-full max-w-xs m-4',
                       'accept': 'image/*'}),

        }


class OpeningHoursForm(forms.Form):
    open_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                'id': 'open_time',
                'class': 'input input-bordered',
                'type': 'time'
            }
        ),
        label="Start hour",
    )

    close_time = forms.TimeField(
        required=True,
        widget=forms.TimeInput(
            attrs={
                'id': 'close_time',
                'class': 'input input-bordered',
                'type': 'time'
            }
        ),
        label="End hour",
    )


class ResourceForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter Resource Name'}),
        max_length=50,
        label="Resource Name"
    )
    capacity = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter Capacity'}),
        min_value=1,
        label="Capacity"
    )

    def __init__(self, *args, queue=None, **kwargs):
        """
        Adjust fields based on queue category.
        :param queue: The queue instance determining the category.
        """
        super().__init__(*args, **kwargs)

        # Dynamically adjust fields based on the queue category
        if queue:
            if queue.category == 'hospital':
                self.fields['specialty'] = forms.ChoiceField(
                    choices=Doctor.MEDICAL_SPECIALTY_CHOICES,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full'}),
                    label="Medical Specialty",
                    required=True
                )



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
