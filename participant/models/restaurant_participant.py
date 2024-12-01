from participant.models import Participant
from django.db import models


class RestaurantParticipant(Participant):
    """Represents a participant in a restaurant queue with table assignment capabilities."""
    SERVICE_TYPE_CHOICE = [
        ('dine_in', 'Dine-in'),
        ('takeout', 'Takeout'),
        ('delivery', 'Delivery'),
    ]
    party_size = models.PositiveIntegerField(default=1)
    service_type = models.CharField(max_length=20,
                                    choices=SERVICE_TYPE_CHOICE,
                                    default='dine_in')
