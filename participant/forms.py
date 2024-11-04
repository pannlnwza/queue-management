from django import forms


class ReservationForm(forms.Form):
    name = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'Enter Your Name'}),
        max_length=50
    )
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'input input-bordered w-full', 'placeholder': 'sample@gmail.com'})
    )
    party_size = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': "input input-bordered w-full",
                                        'placeholder': 'How many people are coming?'})
    )
    note = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'input input-bordered w-full',
                                      'placeholder': "Additional notes or requests (optional)"})
    )
