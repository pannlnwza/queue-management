import math
import string
import random

from django.db.models import ManyToManyField
from django.utils import timezone
from django.db import models
from django.templatetags.static import static
from django.contrib.auth.models import User
from django.urls import reverse
from django.conf import settings
from manager.utils.helpers import format_duration


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
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True,
                                   blank=True)
    authorized_user = models.ManyToManyField(User, related_name='queues',
                                             blank=True)
    open_time = models.DateTimeField(null=True, blank=True)
    close_time = models.DateTimeField(null=True, blank=True)
    estimated_wait_time_per_turn = models.PositiveIntegerField(default=0)
    average_service_duration = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.localtime)
    is_closed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default='normal')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    logo = models.ImageField(upload_to='queue_logos/', blank=True, null=True)
    completed_participants_count = models.PositiveIntegerField(default=0)
    code = models.CharField(max_length=6, unique=True, editable=False)
    latitude = models.FloatField()
    longitude = models.FloatField()

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
            if not Queue.objects.filter(code=code).exists():
                return code

    def has_resources(self):
        return self.category != 'general'

    def get_resources_by_status(self, status):
        return self.resource_set.filter(
            status=status
        )

    def update_estimated_wait_time_per_turn(self, time_taken: int) -> None:
        """Update the estimated wait time per turn based on the time taken for a turn."""
        total_time = (
                             self.estimated_wait_time_per_turn * self.completed_participants_count) + time_taken
        self.completed_participants_count += 1
        self.estimated_wait_time_per_turn = math.ceil(
            total_time / self.completed_participants_count)
        self.save()

    def calculate_average_service_duration(self, serve_time: int):
        """Update the average serve duration based on recent serve time."""
        if self.completed_participants_count > 0:
            total_serve_time = (
                                       self.average_service_duration * self.completed_participants_count) + serve_time
            self.completed_participants_count += 1
            self.average_service_duration = math.ceil(
                total_serve_time / self.completed_participants_count)
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
            'restaurant': static(
                'participant/images/restaurant_default_logo.png'),
            'bank': static('participant/images/bank_default_logo.jpg'),
            'general': static('participant/images/general_default_logo.png'),
            'hospital': static('participant/images/hospital_default_logo.jpg'),
            'service center': static(
                'participant/images/service_center_default_logo.png')
        }
        return default_logos.get(str(self.category))

    def edit(self, name: str = None, description: str = None,
             is_closed: bool = None, status: str = None) -> None:
        """Edit the queue's name, description, or closed status."""
        if name:
            if not (1 <= len(name) <= 255):
                raise ValueError(
                    "The name must be between 1 and 255 characters.")
            self.name = name
        if description is not None:
            self.description = description
        if is_closed is not None:
            self.is_closed = is_closed
        if status in dict(self.STATUS_CHOICES):
            self.status = status
        self.save()

    def get_available_resource(self, required_capacity=1):
        """
        Fetch an available resource for the specified queue.
        It finds a resource with enough capacity that is currently empty.
        """
        return self.resource_set.filter(
            status='available',
            capacity__gte=required_capacity
        ).first()

    def get_join_link(self):
        """
        Returns the full URL to the welcome page for this queue.
        """
        return f"{settings.SITE_DOMAIN}/welcome/{self.code}/"

    def get_number_waiting_now(self):
        """Return the number of participants currently waiting."""
        return self.participant_set.filter(state='waiting').count()

    def get_number_serving_now(self):
        """Return the number of participants currently serving."""
        return self.participant_set.filter(state='serving').count()

    def get_number_served(self):
        """Return the number of participants served."""
        return self.participant_set.filter(state='completed').count()

    def get_number_dropoff(self):
        """Return the number of dropout participants (cancelled, and removed)."""
        return self.participant_set.filter(
            state__in=['cancelled', 'removed']).count()

    def get_served_percentage(self):
        """Return percentage of participants served."""
        num_participants = self.get_number_of_participants()
        return round((self.get_number_served() / num_participants) * 100,
                     2) if num_participants else 0

    def get_dropoff_percentage(self):
        """Return percentage of dropout participants."""
        num_participants = self.get_number_of_participants()
        return round((self.get_number_dropoff() / num_participants) * 100,
                     2) if num_participants else 0

    def get_unattended_percentage(self):
        """Return percentage of unattended participants."""
        num_participants = self.get_number_of_participants()
        return round(
            100 - self.get_dropoff_percentage() - self.get_served_percentage(),
            2) if num_participants else 0

    def get_cancelled_percentage(self) -> float:
        return self._get_substate_percentage('cancelled')

    def get_removed_percentage(self) -> float:
        return self._get_substate_percentage('removed')

    def _get_substate_percentage(self, state: str) -> float:
        dropoff_total = self.get_number_dropoff()
        return round((self.participant_set.filter(
            state=state).count() / dropoff_total) * 100,
                     2) if dropoff_total else 0

    def get_average_waiting_time(self):
        """Calculate the average waiting time for participants in minutes."""
        waiting_times = [
            p.get_wait_time() for p in
            self.participant_set.exclude(state='waiting')
            if p.get_wait_time() is not None
        ]
        average_wait_time = math.ceil(
            sum(waiting_times) / len(waiting_times)) if waiting_times else 0
        return format_duration(average_wait_time)

    def get_max_waiting_time(self):
        """Calculate the maximum waiting time for participants in minutes."""
        waiting_times = [
            p.get_wait_time() for p in
            self.participant_set.exclude(state='waiting')
            if p.get_wait_time() is not None
        ]
        max_wait_time = max(waiting_times) if waiting_times else 0
        return format_duration(max_wait_time)

    def get_average_service_duration(self):
        """Calculate the average service duration for participants in minutes."""
        service_durations = [
            p.get_service_duration() for p in
            self.participant_set.filter(state='completed')
            if p.get_service_duration() is not None
        ]
        average_service_time = math.ceil(sum(service_durations) / len(
            service_durations)) if service_durations else 0
        return format_duration(average_service_time)

    def get_max_service_duration(self):
        """Get the maximum service duration for participants in minutes."""
        service_durations = [
            p.get_service_duration() for p in
            self.participant_set.filter(state='completed')
            if p.get_service_duration() is not None
        ]
        max_service_time = max(service_durations) if service_durations else 0
        return format_duration(max_service_time)

    def record_line_length(self):
        """Records the current line length when a participant joins the queue."""
        line_length = self.participant_set.filter(state='waiting').count()
        QueueLineLength.objects.create(queue=self, line_length=line_length)

    def get_peak_line_length(self):
        """Calculate the peak line length (maximum number of participants waiting) in the queue."""
        peak_record = QueueLineLength.objects.filter(queue=self).order_by(
            '-line_length').first()
        return peak_record.line_length if peak_record else 0

    def get_avg_line_length(self):
        """Calculate the average line length (average number of participants waiting) in the queue."""
        line_lengths = QueueLineLength.objects.filter(queue=self)
        total_records = line_lengths.count()
        if total_records == 0:
            return 0
        total_line_length = sum(record.line_length for record in line_lengths)
        return math.ceil(total_line_length / total_records)

    def __str__(self) -> str:
        """Return a string representation of the queue."""
        return self.name


class QueueLineLength(models.Model):
    """Records the number of participants in the queue at a given time."""

    queue = models.ForeignKey('Queue', on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    line_length = models.PositiveIntegerField()

    def __str__(self):
        return f"{self.queue.name} at {self.timestamp}: {self.line_length} participants waiting"


class Resource(models.Model):
    RESOURCE_STATUS = [
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable'),
    ]

    name = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField(default=1)
    status = models.CharField(choices=RESOURCE_STATUS, max_length=15,
                              default='available')
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, blank=True,
                              null=True)
    assigned_to = models.ForeignKey('participant.Participant',
                                    on_delete=models.SET_NULL, null=True,
                                    blank=True,
                                    related_name='resource_assignment')

    def assign_to_participant(self, participant, capacity=1) -> None:
        """
        Assigns this resource to the given participant if it is available
        and the capacity matches the participant's needs.
        """
        if self.status != 'available':
            raise ValueError("This resource is not available.")
        if self.capacity < capacity:
            raise ValueError(
                "This resource cannot accommodate the party size.")

        self.status = 'busy'
        self.assigned_to = participant
        self.save()
        participant.resource = self
        participant.save()

    def free(self) -> None:
        """
        Frees the resource, making it available for new assignments.
        """
        if self.status == 'busy' and self.assigned_to:
            self.status = 'available'
            self.assigned_to = None
            self.save()

    def is_assigned(self) -> bool:
        """
        Checks if this resource is currently assigned to a participant.
        """
        return self.assigned_to is not None

    def __str__(self):
        """Return a string representation of the table."""
        return f"{self.name} (Status: {self.status}, Capacity: {self.capacity})"


class Doctor(Resource):
    """Represents a doctor in the hospital queue system."""
    MEDICAL_SPECIALTY_CHOICES = [
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

    specialty = models.CharField(max_length=100,
                                 choices=MEDICAL_SPECIALTY_CHOICES,
                                 default='general')

    def __str__(self):
        return f"Doctor {self.name} - Specialty: {self.get_specialty_display()}"


class Counter(Resource):
    """Represent a counter in the bank."""
    pass


class Table(Resource):
    """Represent a table in the restaurant."""
    pass


class RestaurantQueue(Queue):
    has_outdoor = models.BooleanField(default=False)
    resources = models.ManyToManyField(Table)


class BankQueue(Queue):
    """Represents a queue specifically for bank services."""
    resources = models.ManyToManyField(Counter)

    def __str__(self):
        return f"Bank Queue: {self.name}"


class HospitalQueue(Queue):
    resources = models.ManyToManyField(Doctor)


class UserProfile(models.Model):
    """Represents a user profile in the system."""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    phone_no = models.CharField(max_length=15)

    def __str__(self) -> str:
        """Return a string representation of the user profile."""
        return self.user.username
