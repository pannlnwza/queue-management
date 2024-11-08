from django import forms
from .models import Queue  # Assuming Queue model is in the same app

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
            'logo': 'Logo (Optional)',
        }
        widgets = {
            'name': forms.TextInput(attrs={'class': 'input input-bordered w-full max-w-xs"', 'placeholder': 'Enter Queue Name (Max Length: 50)'}),
            'description': forms.Textarea(attrs={'class': 'textarea textarea-bordered', 'placeholder': 'Enter Description (Max Length: 100)', 'rows': 4}),
            'category': forms.Select(attrs={'class': 'select select-bordered w-full max-w-xs m-2'}),
            'logo': forms.ClearableFileInput(attrs={'class': 'file-input w-full max-w-xs m-2', 'accept': 'image/*'}),
        }
