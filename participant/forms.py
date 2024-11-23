# forms.py
from django import forms
from participant.models import RestaurantParticipant, HospitalParticipant, BankParticipant


class KioskForm(forms.Form):
    # Common fields for all categories
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter Your Name'}),
        max_length=50
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'sample@gmail.com'}), required=False
    )
    phone = forms.CharField(
        widget=forms.TextInput(
            attrs={'class': 'input input-bordered w-full', 'placeholder': 'ex. 086-652-xxxx'}),
        max_length=15,
        required=False,
    )

    def __init__(self, *args, queue=None, **kwargs):
        super().__init__(*args, **kwargs)

        # Add specific fields for each queue category
        if queue:
            if queue.category == 'restaurant':
                self.fields['special_1'] = forms.IntegerField(
                    widget=forms.NumberInput(
                        attrs={'class': "input input-bordered w-full", 'placeholder': 'How many people?'}),
                        label='Party Size',
                )
                self.fields['special_2'] = forms.ChoiceField(
                    choices=RestaurantParticipant.SERVICE_TYPE_CHOICE,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full select-md'}),
                    required=False,
                    initial='first_available',
                    label='Seating Preference',
                )
            elif queue.category == 'hospital':
                self.fields['special_1'] = forms.ChoiceField(
                    choices=HospitalParticipant.MEDICAL_FIELD_CHOICES,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full select-md max-w-xs'}),
                    required=True,
                    label="Medical Field",
                )
                self.fields['special_2'] = forms.ChoiceField(
                    choices=HospitalParticipant.PRIORITY_CHOICES,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full select-md max-w-xs'}),
                    required=True,
                    label='Priority Level',
                )
            elif queue.category == 'bank':
                self.fields['special_1'] = forms.ChoiceField(
                    choices=BankParticipant.PARTICIPANT_CATEGORY_CHOICES,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full select-md max-w-xs'}),
                    required=True,
                    label="Select Your Participant Type",
                )
                self.fields['special_2'] = forms.ChoiceField(
                    choices=BankParticipant.SERVICE_TYPE_CHOICES,
                    widget=forms.Select(attrs={'class': 'select select-bordered w-full select-md max-w-xs'}),
                    required=False,
                    label='Select Service Type',
                )
            self.fields['note'] = forms.CharField(
                required=False,
                widget=forms.TextInput(
                    attrs={'class': 'input input-bordered w-full', 'placeholder': "Additional notes"})
            )
