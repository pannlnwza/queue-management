import math
import string
import random
from django.contrib.auth.models import User
from django.db import models
from django.templatetags.static import static
from django.utils import timezone

from participant.models import Participant


# Create your models here.
class Queue(models.Model):
    """Represents a queue created by a user."""
    STATUS_CHOICES = [
        ('normal', 'Normal'),
        ('busy', 'Busy'),
        ('full', 'Full'),
    ]
    CATEGORY_CHOICES = [
        ('restaurant', 'Restaurant'),
        ('general', 'General'),
        ('hospital', 'Hospital'),
        ('bank', 'Bank'),
        ('service center', 'Service center')
    ]
    name = models.CharField(max_length=255)
    description = models.TextField(max_length=100)
    estimated_wait_time_per_turn = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True,
                                   blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_closed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default='normal')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    logo = models.ImageField(upload_to='queue_logos/', blank=True, null=True)
    capacity = models.PositiveIntegerField(null=False)
    completed_participants_count = models.PositiveIntegerField(default=0)
    code = models.CharField(max_length=6, unique=True, editable=False)

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

    def update_estimated_wait_time_per_turn(self, time_taken: int) -> None:
        """Update the estimated wait time per turn based on the time taken for the notified participant.

        :param time_taken: Time taken for the participant to finish their turn in minutes.
        """
        if self.completed_participants_count > 0:
            self.estimated_wait_time_per_turn = math.ceil((self.estimated_wait_time_per_turn * self.completed_participants_count) + time_taken) / (self.completed_participants_count + 1)
        else:
            self.estimated_wait_time_per_turn = time_taken

        # Increment the count of completed participants
        self.completed_participants_count += 1
        self.save()
        print(self.estimated_wait_time_per_turn)

    def get_participants(self) -> models.QuerySet:
        """
        Return a queryset of all participants in this queue.
        :returns: A queryset containing all participants of the queue.
        """
        return self.participant_set.all()

    def get_number_of_participants(self) -> int:
        """
        Return a queryset of all participants in this queue.
        :returns: A queryset containing all participants of the queue.
        """
        return self.participant_set.count()

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

    def get_logo_url(self):
        """Get a logo url for queue."""
        if self.logo:
            return self.logo.url
        default_logos = {
            'restaurant': static(
                'participant/images/restaurant_default_logo.png'),
            'bank': static('participant/images/bank_default_logo.jpg'),
            'general': static('participant/images/general_default_logo.png'),
            'hospital': static('participant/images/hospital_default_logo.jpg'),
            'service center': static('participant/images/service_center_default_logo.png')
        }
        return default_logos.get(str(self.category))

    def is_full(self):
        """Check if the queue is full."""
        return self.participant_set.count() >= self.capacity

    def edit(self, name: str = None, description: str = None,
             is_closed: bool = None, status: str = None) -> None:
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
                raise ValueError(
                    "The name must be between 1 and 255 characters.")
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
        participant_count = self.get_number_of_participants()
        if self.capacity > 0:
            percentage_full = (participant_count / self.capacity) * 100
            if percentage_full >= 70:
                return "Very Busy"
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
    user_type = models.CharField(max_length=20,
                                 choices=[('creator', 'Queue Creator'),
                                          ('participant', 'Participant')])
    phone_no = models.CharField(max_length=15)

    def __str__(self) -> str:
        """
        Return a string representation of the user profile.
        :returns: The username of the user associated with the profile.
        """
        return self.user.username
