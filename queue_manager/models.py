import string
import random
from django.utils import timezone
from django.db import models
from django.contrib.auth.models import User


class Queue(models.Model):
    """Represents a queue created by a user."""
    STATUS_CHOICES = [
        ('normal', 'Normal'),
        ('busy', 'Busy'),
        ('full', 'Full'),
    ]
    name = models.CharField(max_length=255)
    description = models.TextField()
    # code = models.CharField(max_length=6, unique=True, editable=False)
    estimated_wait_time = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='open')
    capacity = models.PositiveIntegerField(null=False, blank=False)

    def update_estimated_wait_time(self, average_time_per_participant: int) -> None:
        """Update the estimated wait time based on the number of participants.

        :param average_time_per_participant: Average time per participant in minutes.
        :raises ValueError: If the average time per participant is negative.
        """
        if average_time_per_participant < 0:
            raise ValueError("Average time per participant cannot be negative.")

        num_participants = self.participant_set.count()
        self.estimated_wait_time = num_participants * average_time_per_participant
        self.save()

    def get_participants(self) -> models.QuerySet:
        """
        Return a queryset of all participants in this queue.
        :returns: A queryset containing all participants of the queue.
        """
        return self.participant_set.all()

    def get_first_participant(self) -> 'Participant':
        """
        Get the participant next in line (i.e., with the lowest position).
        :returns: The participant object with the lowest position in the queue.
        """
        return self.participant_set.order_by('position').first()

    def get_participants_today(self) -> int:
        """
        Get the total number of participants added to the queue today.
        :return: Number of participants added today.
        """
        today = timezone.now().date()
        return self.participant_set.filter(joined_at__date=today).count()

    def is_full(self):
        """Check if the queue is full."""
        return self.participant_set.count() >= self.capacity

    def edit(self, name: str = None, description: str = None, is_closed: bool = None, status: str = None) -> None:
        """
        Edit the queue's name, description, or closed status.

        :param name: The new name for the queue (optional).
        :param description: The new description for the queue (optional).
        :param is_closed: The new closed status (optional).
        :param status: The new status for the queue (optional).
        :raises ValueError: If any of the provided data is invalid.
        """
        if name is not None:
            if len(name) < 1 or len(name) > 255:
                raise ValueError("The name must be between 1 and 255 characters.")
            self.name = name
        if description is not None:
            self.description = description

        if is_closed is not None:
            self.is_closed = is_closed

        if status is not None and status in dict(self.STATUS_CHOICES):
            self.status = status

        self.save()

    @property
    def queue_status(self):
        """
        Calculate the status of the queue based on the percentage of participants
        compared to its capacity.

        Returns:
            str: "Very Busy" if the queue is 70% full or more,
                 "Moderate Busy" if it is between 40% and 70% full,
                 "Little Busy" if it is less than 40% full.
        """
        participant_count = self.participant_set.count()
        if self.capacity > 0:
            percentage_full = (participant_count / self.capacity) * 100
            if percentage_full >= 70:
                return "Very busy"
            elif percentage_full >= 40:
                return "Moderate Busy"
            else:
                return "Not Busy"

    def __str__(self) -> str:
        """
        Return a string representation of the queue.
        :returns: The name of the queue.
        """
        return self.name


class UserProfile(models.Model):
    """Represents a user profile in the system."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    user_type = models.CharField(max_length=20, choices=[('creator', 'Queue Creator'), ('participant', 'Participant')])
    phone_no = models.CharField(max_length=15)

    def __str__(self) -> str:
        """
        Return a string representation of the user profile.
        :returns: The username of the user associated with the profile.
        """
        return self.user.username


class Participant(models.Model):
    """Represents a participant in a queue."""
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True)
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE)
    joined_at = models.DateTimeField(null=True)
    position = models.PositiveIntegerField(null=True)
    queue_code = models.CharField(max_length=6, unique=True, editable=False)

    class Meta:
        unique_together = ('user', 'queue')

    def insert_user(self, user):
        self.user = user
        self.joined_at = timezone.now()

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
        average_service_time_per_participant = self.queue.estimated_wait_time
        return average_service_time_per_participant * self.position

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
