from django import forms
from .models import Queue, UserProfile, Resource, Doctor
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class QueueForm(forms.ModelForm):
    """
    Form for creating or updating a Queue instance.
    """

    class Meta:
        model = Queue
        fields = ['name', 'description', 'category']  # Exclude 'logo'
        labels = {
            'description': 'Description (Optional)',
        }
        widgets = {
            'name': forms.TextInput(
                attrs={
                    'class': 'input input-bordered w-full max-w-xs m-4',
                    'placeholder': 'Enter Queue Name (Max Length: 50)',
                }),
            'description': forms.Textarea(
                attrs={
                    'class': 'textarea textarea-bordered w-full m-4',
                    'placeholder': 'About This Queue (Max Length: 255)',
                    'rows': 4,
                }),
            'category': forms.Select(
                attrs={'class': 'select select-bordered w-full max-w-xs m-4'}
            ),
        }


class OpeningHoursForm(forms.Form):
    open_time = forms.TimeField(
        required=False,
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
        required=False,
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

    def __init__(self, *args, queue_category=None, **kwargs):
        """
        Adjust fields based on queue category.
        :param queue_category: The category of the queue to dynamically adjust fields.
        """
        super().__init__(*args, **kwargs)
        self.category = queue_category['category']

        if self.category != 'general':
            # Add dynamic fields and instance variables based on queue_category

            input_style = 'input input-bordered w-full m-4 text-m'
            self.fields['name'] = forms.CharField(
                widget=forms.TextInput(attrs={'class': input_style, 'placeholder': 'Enter Name'}),
                max_length=50,
            )
            self.fields['status'] = forms.ChoiceField(
                choices=Resource.RESOURCE_STATUS,
                widget=forms.Select(attrs={'class': 'select select-bordered w-full m-4'}),
                label="Status",
                required=True
            )
            if queue_category['category'] == 'hospital':
                self.fields['special'] = forms.ChoiceField(
                    choices=Doctor.MEDICAL_SPECIALTY_CHOICES,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full m-4'}),
                    label="Medical Specialty",
                    required=True,
                )
                self.resource_name = "Specialist"
            elif queue_category['category'] == 'restaurant':
                self.fields['special'] = forms.IntegerField(
                widget=forms.NumberInput(attrs={'class': input_style, 'placeholder': 'Enter Capacity'}),
                min_value=1,
                label="Capacity"
            )
                self.resource_name = "Table"
            elif queue_category['category'] == 'bank':
                self.resource_name = "Counter"

        else:
            self.resource_name = "Resource"

    def get_resource_name(self):
        """
        A helper method to access resource name dynamically.
        """
        return self.resource_name





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
    remove_image = forms.CharField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = UserProfile
        fields = ['username', 'email', 'phone', 'image', 'first_name', 'last_name']
