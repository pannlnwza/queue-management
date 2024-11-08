from django import forms


class ReservationForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter Your Name'}),
        max_length=50
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'sample@gmail.com'})
    )
    phone = forms.CharField(
        widget=forms.TextInput(
            attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter Your Phone Number'}),
        max_length=15,
        required=False,  # Optional, set to True if you want to make the field required
        help_text="Format: (xxx) xxx-xxxx"  # Optional help text for formatting
    )
    party_size = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': "input input-bordered w-full",
                                        'placeholder': 'How many people are coming?'})
    )
    seating_preference = forms.ChoiceField(
        choices=[
            ('first_available', 'First Available'),
            ('indoor', 'Indoor'),
            ('outdoor', 'Outdoor')
        ],
        widget=forms.Select(attrs={'class': 'select select-bordered w-full select-md max-w-xs'}),
        required=False,  # You can set it to required=True if you want to enforce a choice
        initial='first_available'  # Default choice can be set to 'first_available'
    )
    note = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full',
                                      'placeholder': "Additional notes or requests (optional)"})
    )

