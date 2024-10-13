# queue_manager/forms.py

from django import forms
from .models import Queue


class QueueForm(forms.ModelForm):
    class Meta:
        model = Queue
        fields = ['name', 'description']  # Fields you want the user to fill out
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Queue Name'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'placeholder': 'Enter Description', 'rows': 4}),
        }

