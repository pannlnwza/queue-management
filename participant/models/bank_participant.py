from django.db import models
from participant.models import Participant

class BankParticipant(Participant):
    """Represents a participant in a bank queue with specific service complexity and service type needs."""

    SERVICE_TYPE_CHOICES = [
        ('account_services', 'Account Services'),
        ('loan_services', 'Loan Services'),
        ('investment_services', 'Investment Services'),
        ('customer_support', 'Customer Support'),
    ]

    PARTICIPANT_CATEGORY_CHOICES = [
        ('individual', 'Individual'),
        ('business', 'Business'),
        ('corporate', 'Corporate'),
        ('government', 'Government'),
    ]

    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
        default='account_services',
    )
    participant_category = models.CharField(max_length=20, choices=PARTICIPANT_CATEGORY_CHOICES, default='individual')