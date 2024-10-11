import string
import random
from django.db import models
from django.contrib.auth.models import User


class Queue(models.Model):
    """Represents a queue created by a user."""
    name = models.CharField(max_length=255)
    description = models.TextField()
    code = models.CharField(max_length=6, unique=True, editable=False)
    estimated_wait_time = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs) -> None:
        """Save the queue instance. Generates a unique code if it doesn't already exist."""
        if not self.code:
            self.code = self.generate_unique_code()
        super().save(*args, **kwargs)

    def update_estimated_wait_time(self, average_time_per_participant: int) -> None:
        """Update the estimated wait time based on the number of participants."""
        if average_time_per_participant < 0:
            raise ValueError("Average time per participant cannot be negative.")

        num_participants = self.participant_set.count()
        self.estimated_wait_time = num_participants * average_time_per_participant
        self.save()

    def get_participants(self) -> models.QuerySet:
        """Return a queryset of all participants in this queue."""
        return self.participant_set.all()

    def get_first_participant(self) -> 'Participant':
        """Get the participant next in line (i.e., with the lowest position)."""
        return self.participant_set.order_by('position').first()

    def __str__(self) -> str:
        """Return a string representation of the queue."""
        return self.name

    @staticmethod
    def generate_unique_code(length: int = 6) -> str:
        """Generate a unique code consisting of uppercase letters and digits."""
        characters = string.ascii_uppercase + string.digits
        while True:
            code = ''.join(random.choices(characters, k=length))
            if not Queue.objects.filter(code=code).exists():
                return code


class UserProfile(models.Model):
    """Represents a user profile in the system."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=[('creator', 'Queue Creator'), ('participant', 'Participant')])
    phone_no = models.CharField(max_length=15)

    def __str__(self) -> str:
        """Return a string representation of the user profile."""
        return self.user.username


class Participant(models.Model):
    """Represents a participant in a queue."""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    position = models.PositiveIntegerField(unique=True)

    class Meta:
        unique_together = ('user', 'queue')

    def update_position(self, new_position: int) -> None:
        """Update the position of the participant in the queue."""
        if new_position < 0:
            raise ValueError("Position cannot be negative.")
        self.position = new_position
        self.save()

    def __str__(self) -> str:
        """Return a string representation of the participant."""
        return self.user.username
