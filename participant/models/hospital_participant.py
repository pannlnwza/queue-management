from django.db import models
from participant.models import Participant


class HospitalParticipant(Participant):
    """Represents a participant in a hospital queue."""
    MEDICAL_FIELD_CHOICES = [
        ('cardiology', 'Cardiology'),
        ('neurology', 'Neurology'),
        ('orthopedics', 'Orthopedics'),
        ('dermatology', 'Dermatology'),
        ('pediatrics', 'Pediatrics'),
        ('general', 'General Medicine'),
        ('emergency', 'Emergency'),
        ('psychiatry', 'Psychiatry'),
        ('surgery', 'Surgery'),
        ('oncology', 'Oncology'),
    ]

    PRIORITY_CHOICES = [
        ('urgent', 'Urgent'),
        ('normal', 'Normal'),
        ('low', 'Low'),
    ]
    medical_field = models.CharField(max_length=50,
                                     choices=MEDICAL_FIELD_CHOICES,
                                     default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES,
                                default='normal')

    def __str__(self):
        return f"Hospital Participant: {self.name}"