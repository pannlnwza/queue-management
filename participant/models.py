import random
import string

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Participant(models.Model):
    """Represents a participant in a queue."""
    PARTICIPANT_STATE = [
        ('waiting', 'Waiting'),
        ('serving', 'Serving'),
        ('completed', 'Completed'),
    ]

    name = models.CharField(max_length=30)
    email = models.EmailField(max_length=50, null=True, blank=True)
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    joined_at = models.DateTimeField(default=timezone.localtime)
    position = models.PositiveIntegerField(null=True)
    note = models.TextField(max_length=150, null=True, blank=True)
    code = models.CharField(max_length=6, unique=True, editable=False)
    state = models.CharField(max_length=10, choices=PARTICIPANT_STATE, default='waiting')
    service_started_at = models.DateTimeField(null=True, blank=True)
    service_completed_at = models.DateTimeField(null=True, blank=True)

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

    def complete_service(self):
        """Mark the participant as completed."""
        if self.state == 'serving':
            self.state = 'completed'
            self.service_completed_at = timezone.localtime()
            self.save()

    def get_wait_time(self):
        """Calculate the wait time for the participant."""
        if self.state == 'waiting':
            return int((timezone.localtime() - self.joined_at).total_seconds() / 60)
        elif self.state == 'serving' and self.service_started_at:
            return int((self.service_started_at - self.joined_at).total_seconds() / 60)
        return 0

    def get_service_duration(self):
        """Calculate the duration of service for the participant."""
        if self.state == 'serving' and self.service_started_at:
            return int((timezone.localtime() - self.service_started_at).total_seconds() / 60)
        elif self.state == 'completed':
            if self.service_started_at and self.service_completed_at:
                return int((self.service_completed_at - self.service_started_at).total_seconds() / 60)
        return 0

    def __str__(self) -> str:
        """Return a string representation of the participant."""
        return f"{self.name} - {self.state}"


class Notification(models.Model):
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)


    def __str__(self):
        return f"Notification for {self.participant}: {self.message}"

