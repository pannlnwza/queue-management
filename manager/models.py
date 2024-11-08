import math
import string
import random

from django.utils import timezone
from django.db import models
from django.templatetags.static import static
from django.contrib.auth.models import User


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

    name = models.CharField(max_length=50)
    description = models.TextField(max_length=60)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    authorized_user = models.ManyToManyField(User, related_name='queues', blank=True)
    open_time = models.DateTimeField(null=True, blank=True)
    close_time = models.DateTimeField(null=True, blank=True)
    estimated_wait_time_per_turn = models.PositiveIntegerField(default=0)
    average_service_duration = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.localtime)
    is_closed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='normal')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    logo = models.ImageField(upload_to='queue_logos/', blank=True, null=True)
    completed_participants_count = models.PositiveIntegerField(default=0)

    def update_estimated_wait_time_per_turn(self, time_taken: int) -> None:
        """Update the estimated wait time per turn based on the time taken for a turn."""
        total_time = (self.estimated_wait_time_per_turn * self.completed_participants_count) + time_taken
        self.completed_participants_count += 1
        self.estimated_wait_time_per_turn = math.ceil(total_time / self.completed_participants_count)
        self.save()

    def calculate_average_service_duration(self, serve_time: int):
        """Update the average serve duration based on recent serve time."""
        if self.completed_participants_count > 0:
            total_serve_time = (self.average_service_duration * self.completed_participants_count) + serve_time
            self.completed_participants_count += 1
            self.average_service_duration = math.ceil(total_serve_time / self.completed_participants_count)
        else:
            self.average_service_duration = serve_time
            self.completed_participants_count += 1
        self.save()

    def get_participants(self) -> models.QuerySet:
        """Return a queryset of all participants in this queue."""
        return self.participant_set.all()

    def get_number_of_participants(self) -> int:
        """Return the count of all participants in this queue."""
        return self.participant_set.count()

    def get_participants_today(self) -> int:
        """Get the total number of participants added to the queue today."""
        today = timezone.now().date()
        return self.participant_set.filter(joined_at__date=today).count()

    def get_logo_url(self):
        """Get a logo URL for the queue, or return a default logo based on category."""
        if self.logo:
            return self.logo.url
        default_logos = {
            'restaurant': static('participant/images/restaurant_default_logo.png'),
            'bank': static('participant/images/bank_default_logo.jpg'),
            'general': static('participant/images/general_default_logo.png'),
            'hospital': static('participant/images/hospital_default_logo.jpg'),
            'service center': static('participant/images/service_center_default_logo.png')
        }
        return default_logos.get(str(self.category))

    def edit(self, name: str = None, description: str = None, is_closed: bool = None, status: str = None) -> None:
        """Edit the queue's name, description, or closed status."""
        if name:
            if not (1 <= len(name) <= 255):
                raise ValueError("The name must be between 1 and 255 characters.")
            self.name = name
        if description is not None:
            self.description = description
        if is_closed is not None:
            self.is_closed = is_closed
        if status in dict(self.STATUS_CHOICES):
            self.status = status
        self.save()

    def __str__(self) -> str:
        """Return a string representation of the queue."""
        return self.name


class Table(models.Model):
    TABLE_STATUS = [
        ('empty', 'Empty'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable'),
    ]

    name = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField(default=1)
    status = models.CharField(choices=TABLE_STATUS, max_length=15, default='empty')
    party = models.ForeignKey('participant.RestaurantParticipant', on_delete=models.SET_NULL, null=True, blank=True,
                              related_name='table_assignment')

    def assign_to_party(self, participant) -> None:
        """Assigns this table to the given participant if it is available and the capacity matches the party size."""
        if self.status == 'empty' and self.capacity >= participant.party_size:
            self.status = 'busy'
            self.party = participant
            self.save()
            participant.table = self
            participant.save()
        elif self.capacity < participant.party_size:
            raise ValueError("This table cannot accommodate the party size.")
        else:
            raise ValueError("This table is not available.")

    def free(self) -> None:
        """Frees the table, making it available for new assignments."""
        if self.status == 'busy':
            self.status = 'empty'
            self.party = None
            self.save()

    def is_assigned(self) -> bool:
        """Checks if this table has an assigned participant."""
        return self.party is not None

    def change_party(self, new_participant) -> None:
        """
        Reassigns the table to a new participant if it is available and matches the capacity requirements.
        """
        if self.is_assigned():
            if self.party.queue != new_participant.queue:
                raise ValueError("The new participant must be in the same queue as the current assignment.")
            self.free()
        self.assign_to_party(new_participant)

    def __str__(self):
        """Return a string representation of the table."""
        return f"{self.name} (Status: {self.status}, Capacity: {self.capacity})"


class RestaurantQueue(Queue):
    tables = models.ManyToManyField(Table)
    has_outdoor = models.BooleanField(default=False)


class UserProfile(models.Model):
    """Represents a user profile in the system."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_no = models.CharField(max_length=15)

    def __str__(self) -> str:
        """Return a string representation of the user profile."""
        return self.user.username