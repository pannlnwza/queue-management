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
        fields = ['name', 'description', 'estimated_wait_time']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter Queue Name'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'placeholder': 'Enter Description', 'rows': 4}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control',
                                                 'placeholder': 'Enter Queue Capacity'}),
            'estimated_wait_time': forms.NumberInput(attrs={'class': 'form-control',
                                                            'placeholder': 'Enter Estimated Wait Time (minutes)'}),
        }

    name = forms.CharField(required=True, error_messages={
        'required': 'Please enter a name for the queue.'})
    estimated_wait_time = forms.IntegerField(required=True, error_messages={
        'required': 'Please enter an estimated wait time.'})
    capacity = forms.IntegerField(required=True, error_messages={
        'required': 'Please enter a capacity for the queue.'})
    description = forms.CharField(required=False)
