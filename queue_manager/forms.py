from django import forms
from .models import Queue


class QueueForm(forms.ModelForm):
    """
    Form for creating or updating a Queue instance.

    This form allows users to input the necessary details for a queue,
    including its name and description.
    """

    class Meta:
        model = Queue
        fields = ['name', 'logo', 'description', 'category', 'estimated_wait_time']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Queue Name'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'placeholder': 'Enter Description', 'rows': 4}),
            'category': forms.Select(choices=Queue.CATEGORY_CHOICES),
            'estimated_wait_time': forms.NumberInput(attrs={'class': 'form-control',
                                                            'placeholder': 'Enter Estimated Wait Time (minutes)'}),
            'logo': forms.ClearableFileInput(
                attrs={'class': 'form-control', 'accept': 'image/*'})
        }

