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
        fields = ['name', 'logo', 'description', 'capacity', 'category', 'estimated_wait_time']
        labels = {
            'logo': 'Logo (Optional)',
            'estimated_wait_time': 'Estimated wait time (minutes)'
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Queue Name (Max Length: 50)'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'placeholder': 'Enter Description (Max Length: 100)', 'rows': 4}),
            'category': forms.Select(choices=Queue.CATEGORY_CHOICES),
            'capacity': forms.NumberInput(attrs={'class': 'form-control',
                                                 'placeholder': 'Enter Capacity'}),
            'estimated_wait_time': forms.NumberInput(attrs={'class': 'form-control',
                                                            'placeholder': 'Enter Estimated Wait Time (minutes)'}),
            'logo': forms.ClearableFileInput(
                attrs={'class': 'form-control', 'accept': 'image/*'})
        }
