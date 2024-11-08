import random
import string

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone
from manager.models import RestaurantQueue, BankQueue, Resource, HospitalQueue
from datetime import timedelta


class Participant(models.Model):
    """Represents a participant in a queue."""
    PARTICIPANT_STATE = [
        ('waiting', 'Waiting'),
        ('serving', 'Serving'),
        ('completed', 'Completed'),
    ]

    name = models.CharField(max_length=30)
    email = models.EmailField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    position = models.PositiveIntegerField(null=True)  # why null? right now
    note = models.TextField(max_length=150, null=True, blank=True)
    code = models.CharField(max_length=6, unique=True, editable=False)
    state = models.CharField(max_length=10, choices=PARTICIPANT_STATE, default='waiting')
    service_started_at = models.DateTimeField(null=True, blank=True)
    service_completed_at = models.DateTimeField(null=True, blank=True)
    waited = models.PositiveIntegerField(default=0)
    visits = models.PositiveIntegerField(default=1)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE, blank=True, null=True)


    def save(self, *args, **kwargs):
        """Generate a unique ticket code for the participant if not already."""
        if not self.pk:
            self.code = self.generate_unique_queue_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_queue_code(length=6):
        """Generate a unique code for each participant."""
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=length))
            if not Participant.objects.filter(code=code).exists():
                return code

    def update_position(self, new_position: int) -> None:
        """Update the position of the participant in the queue."""
        if new_position < 1:
            raise ValueError("Position must be positive.")
        self.position = new_position
        self.save()

    def calculate_estimated_wait_time(self) -> int:
        """Calculate the estimated wait time for this participant in the queue."""
        return self.queue.estimated_wait_time_per_turn * (self.position - 1)

    def start_service(self):
        """Mark the participant as serving."""
        if self.state == 'waiting':
            self.state = 'serving'
            self.service_started_at = timezone.localtime()
            self.save()

    def get_wait_time(self):
        """Calculate the wait time for the participant."""
        if self.state == 'waiting':
            return int((timezone.localtime() - self.joined_at).total_seconds() / 60)
        elif self.state == 'serving' and self.service_started_at:
            return int((self.service_started_at - self.joined_at).total_seconds() / 60)

    def get_service_duration(self):
        """Calculate the duration of service for the participant."""
        if self.state == 'serving' and self.service_started_at:
            return int((timezone.localtime() - self.service_started_at).total_seconds() / 60)
        elif self.state == 'completed':
            if self.service_started_at and self.service_completed_at:
                return int((self.service_completed_at - self.service_started_at).total_seconds() / 60)
        return 0

    def assign_to_resource(self, required_capacity=None):
        """
        Assigns this participant to an available resource based on the queue category.
        """
        queue = self.queue
        resource = queue.get_available_resource(required_capacity=required_capacity)

        if resource:
            resource.status = 'busy'
            resource.save()
            self.resource = resource
            self.save()
        else:
            raise ValueError("No available resources")

    @staticmethod
    def remove_old_completed_participants():
        """Remove participants whose service completed 30 days ago"""
        cutoff_time = timezone.localtime() - timedelta(days=30)
        Participant.objects.filter(state='completed', service_completed_at__lte=cutoff_time).delete()

    def __str__(self) -> str:
        """Return a string representation of the participant."""
        return f"{self.name} - {self.state}"




class RestaurantParticipant(Participant):
    """Represents a participant in a restaurant queue with table assignment capabilities."""
    SEATING_PREFERENCES = [
        ('first_available', 'First Available'),
        ('indoor', 'Indoor'),
        ('outdoor', 'Outdoor'),
    ]
    table_served = models.CharField(max_length=20, null=True, blank=True)
    party_size = models.PositiveIntegerField(default=1)
    seating_preference = models.CharField(max_length=20, choices=SEATING_PREFERENCES, default='first_available')

    def save(self, *args, **kwargs):
        """Override save method to enforce seating preference rules based on the queue's availability."""
        if self.queue and isinstance(self.queue, RestaurantQueue):
            if not self.queue.has_outdoor:
                if self.seating_preference not in ['first_available']:
                    raise ValueError(
                        "Seating preference can only be 'First Available' for queues without outdoor seating.")
        super().save(*args, **kwargs)




class BankParticipant(Participant):
    """Represents a participant in a bank queue with specific service complexity and service type needs."""

    SERVICE_TYPE_CHOICES = [
        ('account_services', 'Account Services'),
        ('loan_services', 'Loan Services'),
        ('investment_services', 'Investment Services'),
        ('customer_support', 'Customer Support'),
    ]

    counter_served = models.CharField(max_length=20, null=True, blank=True)
    service_type = models.CharField(
        max_length=20,
        choices=SERVICE_TYPE_CHOICES,
        default='account_services',
    )

    def save(self, *args, **kwargs):
        """Additional validations based on the bank queue's rules."""
        if self.queue and isinstance(self.queue, RestaurantQueue):
            raise ValueError("BankParticipant must be assigned to a BankQueue.")
        super().save(*args, **kwargs)


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
    medical_field = models.CharField(max_length=50, choices=MEDICAL_FIELD_CHOICES, default='general')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES,
                                default='normal')

    def __str__(self):
        return f"Hospital Participant: {self.name}"


    def save(self, *args, **kwargs):
        """Additional validations based on the bank queue's rules."""
        if self.queue and isinstance(self.queue, HospitalQueue):
            raise ValueError("HospitalParticipant must be assigned to a BankQueue.")
        super().save(*args, **kwargs)


class Notification(models.Model):
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)


    def __str__(self):
        return f"Notification for {self.participant}: {self.message}"