from django.db import models
from manager.utils.code_generator import generate_unique_code, \
    generate_unique_number
from django.utils import timezone
from manager.models import Resource
from datetime import timedelta
from django.conf import settings


class Participant(models.Model):
    """Represents a participant in a queue."""
    PARTICIPANT_STATE = [
        ('waiting', 'Waiting'),
        ('serving', 'Serving'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
        ('removed', 'Removed'),
        ('no_show', 'No Show')
    ]
    CREATE_BY = [
        ('guest', 'Guest'),
        ('staff', 'Staff')
    ]
    name = models.CharField(max_length=30)
    email = models.EmailField(max_length=50, null=True, blank=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    joined_at = models.DateTimeField(auto_now_add=True)
    position = models.PositiveIntegerField(null=True, blank=True)
    note = models.TextField(max_length=150, null=True, blank=True)
    code = models.CharField(max_length=12, unique=True, editable=False)
    state = models.CharField(max_length=10, choices=PARTICIPANT_STATE,
                             default='waiting')
    service_started_at = models.DateTimeField(null=True, blank=True)
    service_completed_at = models.DateTimeField(null=True, blank=True)
    waited = models.PositiveIntegerField(default=0)
    visits = models.PositiveIntegerField(default=1)
    resource = models.ForeignKey(Resource, on_delete=models.CASCADE,
                                 blank=True, null=True)
    resource_assigned = models.CharField(max_length=20, null=True, blank=True)
    is_notified = models.BooleanField(default=False)
    created_by = models.CharField(max_length=10, choices=CREATE_BY,
                                  default='guest')
    updated_at = models.DateTimeField(blank=True, null=True)
    status_qr_code = models.ImageField(upload_to='qrcodes/', null=True,
                                       blank=True)
    number = models.CharField(max_length=4, editable=False)
    announcement_audio = models.TextField(null=True)
    qrcode_url = models.CharField(max_length=500, blank=True, null=True)
    qrcode_email_sent = models.BooleanField(default=False)

    class Meta:
        unique_together = ('number', 'queue')

    def save(self, *args, **kwargs):
        """Assign unique code and number upon creation."""
        if not self.pk:  # Only set these fields for new instances
            self.code = generate_unique_code(Participant)
            self.number = generate_unique_number(self.queue)
        if not self.position:  # Only set position if it's not already set
            last_position = \
            Participant.objects.aggregate(models.Max('position'))[
                'position__max'] or 0
            self.position = last_position + 1
        self.updated_at = timezone.localtime()
        super().save(*args, **kwargs)

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
            self.position = None
            self.service_started_at = timezone.localtime()
            self.save()

    def get_wait_time(self):
        """Calculate the wait time for the participant."""
        if self.state == 'waiting':
            return int(
                (timezone.localtime() - self.joined_at).total_seconds() / 60)
        elif self.service_started_at:
            return int((
                                   self.service_started_at - self.joined_at).total_seconds() / 60)

    def get_service_duration(self):
        """Calculate the duration of service for the participant."""
        if self.state == 'serving' and self.service_started_at:
            return int((
                                   timezone.localtime() - self.service_started_at).total_seconds() / 60)
        elif self.state == 'completed':
            if self.service_started_at and self.service_completed_at:
                return int((
                                       self.service_completed_at - self.service_started_at).total_seconds() / 60)
        return 0

    def assign_to_resource(self, required_capacity=None):
        """
        Assigns this participant to an available resource based on the queue category.
        """
        queue = self.queue

        # Get the resource, filtering by capacity if provided
        if required_capacity is not None:
            resource = queue.get_available_resource(
                required_capacity=required_capacity)
        else:
            resource = queue.get_available_resource()

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
        Participant.objects.filter(state='completed',
                                   service_completed_at__lte=cutoff_time).delete()

    def get_status_link(self):
        """
        Returns the full URL to the welcome page for this queue.
        """
        return f"{settings.SITE_DOMAIN}status/{self.code}"

    def get_status_print_link(self):
        """
        Returns the full URL to the welcome page for this queue.
        """
        return f"{settings.SITE_DOMAIN}status_for_printing/{self.code}"

    def __str__(self) -> str:
        """Return a string representation of the participant."""
        return f"{self.name} - {self.state}"