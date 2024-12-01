import math
from django.db import models
from django.apps import apps
from manager.utils.helpers import format_duration
from manager.models import Queue


class Resource(models.Model):
    RESOURCE_STATUS = [
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('unavailable', 'Unavailable'),
    ]

    name = models.CharField(max_length=50)
    capacity = models.PositiveIntegerField(default=1)
    status = models.CharField(choices=RESOURCE_STATUS, max_length=15,
                              default='available')
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, blank=True,
                              null=True)
    assigned_to = models.ForeignKey('participant.Participant',
                                    on_delete=models.SET_NULL, null=True,
                                    blank=True,
                                    related_name='resource_assignment')

    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ('name', 'queue')

    def assign_to_participant(self, participant, capacity=1) -> None:
        """
        Assigns this resource to the given participant if it is available
        and the capacity matches the participant's needs.
        """
        if self.status != 'available':
            raise ValueError("This resource is not available.")
        if int(self.capacity) < int(capacity):
            raise ValueError(
                "This resource cannot accommodate the party size.")

        self.status = 'busy'
        self.count += 1
        self.assigned_to = participant
        self.save()
        participant.resource = self
        participant.save()

    def free(self) -> None:
        """
        Frees the resource, making it available for new assignments.
        """
        if self.assigned_to:
            participant = self.assigned_to
            participant.resource = None
            participant.save()

        self.status = 'available'
        self.assigned_to = None
        self.save()

    def is_assigned(self) -> bool:
        """
        Checks if this resource is currently assigned to a participant.
        """
        return self.assigned_to is not None

    def total(self, start_date=None, end_date=None):
        """Return the total number of participants assigned to this resource within a date range."""
        Participant = apps.get_model('participant', 'Participant')
        queryset = Participant.objects.filter(resource_assigned=self.name)
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def served(self, start_date=None, end_date=None):
        """Return the number of participants who are currently being served or have completed service at this resource within a date range."""
        Participant = apps.get_model('participant', 'Participant')
        queryset = Participant.objects.filter(resource_assigned=self.name,
                                              state__in=['serving',
                                                         'completed'])
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def dropoff(self, start_date=None, end_date=None):
        """Return the number of participants who have been removed or cancelled from this resource within a date range."""
        Participant = apps.get_model('participant', 'Participant')
        queryset = Participant.objects.filter(resource_assigned=self.name,
                                              state__in=['removed',
                                                         'cancelled'])
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def completed(self, start_date=None, end_date=None):
        """Return the number of participants who have completed service at this resource within a date range."""
        Participant = apps.get_model('participant', 'Participant')
        queryset = Participant.objects.filter(resource_assigned=self.name,
                                              state='completed')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def avg_wait_time(self, start_date=None, end_date=None):
        """Calculate the average wait time for participants in the 'serving' or 'completed' states at this resource within a date range."""
        Participant = apps.get_model('participant', 'Participant')
        queryset = Participant.objects.filter(resource_assigned=self.name,
                                              state__in=['serving',
                                                         'completed'])
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))

        wait_times = [p.get_wait_time() for p in queryset if
                      p.get_wait_time() is not None]
        average_wait_time = math.ceil(
            sum(wait_times) / len(wait_times)) if wait_times else 0
        return format_duration(average_wait_time)

    def avg_serve_time(self, start_date=None, end_date=None):
        """Calculate the average service duration for participants in the 'completed' state at this resource within a date range."""
        Participant = apps.get_model('participant', 'Participant')
        queryset = Participant.objects.filter(resource_assigned=self.name,
                                              state='completed')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))

        serve_times = [p.get_service_duration() for p in queryset if
                       p.get_service_duration() is not None]
        average_serve_time = math.ceil(
            sum(serve_times) / len(serve_times)) if serve_times else 0
        return format_duration(average_serve_time)

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
        return f"Doctor {self.name} - Specialty: {self.specialty}"


class Counter(Resource):
    """Represent a counter in the bank."""
    SERVICE_TYPE_CHOICES = [
        ('account_services', 'Account Services'),
        ('loan_services', 'Loan Services'),
        ('investment_services', 'Investment Services'),
        ('customer_support', 'Customer Support'),
    ]
    service_type = models.CharField(max_length=100,
                                    choices=SERVICE_TYPE_CHOICES,
                                    default='account_service')


class Table(Resource):
    """Represent a table in the restaurant."""
    pass
