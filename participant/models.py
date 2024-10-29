import random
import string

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

import manager.models


# Create your models here.
class Participant(models.Model):
    """Represents a participant in a queue."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    joined_at = models.DateTimeField(null=True)
    position = models.PositiveIntegerField(null=True)
    queue_code = models.CharField(max_length=6, unique=True, editable=False)

    class Meta:
        unique_together = ('user', 'queue')

    def insert_user(self, user):
        self.user = user
        self.joined_at = timezone.localtime(timezone.now())

    def update_position(self, new_position: int) -> None:
        """
        Update the position of the participant in the queue.

        :param new_position: The new position to assign to the participant.
        :raises ValueError: If the new position is negative.
        """
        if new_position < 0:
            raise ValueError("Position cannot be negative.")
        self.position = new_position
        self.save()

    def update_to_last_position(self):
        last_position = self.queue.participant_set.count()
        self.position = last_position + 1
        self.save()

    def calculate_estimated_wait_time(self):
        """
        Calculate the estimated wait time for this participant in the queue.

        :returns: The estimated wait time in minutes.
        """
        return self.queue.estimated_wait_time_per_turn * self.position

    def save(self,*args, **kwargs):
        """Generate a unique ticket code for the participant if not already."""
        if not self.pk:
            self.queue_code = self.generate_unique_queue_code()
        super().save(*args, **kwargs)

    @staticmethod
    def generate_unique_queue_code(length=6):
        """Generate a unique code for each participant"""
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=length))
            if not Participant.objects.filter(queue_code=code).exists():
                return code

    def __str__(self) -> str:
        """
        Return a string representation of the participant.
        :returns: The username of the user associated with the participant.
        """
        return self.user.username if self.user else "-"


class Notification(models.Model):
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.participant}: {self.message}"


class QueueHistory(models.Model):
    """Represents the history of actions taken on a queue."""

    ACTION_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('canceled', 'Canceled'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    queue_description = models.TextField(max_length=100)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, default='Active')
    joined_at = models.DateTimeField(auto_now_add=True)

    def get_queryset(self):
        return QueueHistory.objects.filter(user=self.request.user).order_by('-joined_at')

    def __str__(self):
        return f"{self.user.username} {self.action} queue {self.queue.name} joined_at {self.joined_at}"
