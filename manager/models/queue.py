from django.db import models
from django.utils import timezone
from django.contrib.auth.models import User
from django.utils.timezone import localtime
from datetime import datetime, timedelta
from manager.utils.code_generator import generate_unique_code
from manager.utils.aws_s3_storage import get_s3_base_url
from manager.utils.helpers import format_duration
from django.core.exceptions import ValidationError
from django.conf import settings
import math
from math import radians, sin, cos, sqrt, atan2



class Queue(models.Model):
    """Represents a queue created by a user."""
    STATUS_CHOICES = [
        ('normal', 'Normal'),
        ('busy', 'Busy'),
        ('full', 'Full'),
    ]
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('restaurant', 'Restaurant'),
        ('hospital', 'Hospital'),
        ('bank', 'Bank'),
    ]

    name = models.CharField(max_length=50)
    description = models.TextField(max_length=255)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True,
                                   blank=True)
    open_time = models.TimeField(null=True, blank=True)
    close_time = models.TimeField(null=True, blank=True)
    estimated_wait_time_per_turn = models.PositiveIntegerField(default=0)
    average_service_duration = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(default=timezone.localtime)
    is_closed = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES,
                              default='normal')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    logo = models.CharField(max_length=500, blank=True, null=True)
    completed_participants_count = models.PositiveIntegerField(default=0)
    code = models.CharField(max_length=12, unique=True, editable=False)
    latitude = models.FloatField()
    longitude = models.FloatField()
    distance_from_user = models.FloatField(null=True, blank=True)
    tts_notifications_enabled = models.BooleanField(default=True)

    def save(self, *args, **kwargs):
        """Generate a unique ticket code for the participant if not already."""
        if not self.pk:
            self.code = generate_unique_code(Queue)
        super().save(*args, **kwargs)

    def is_queue_closed(self):
        """
        Determine if the queue is closed based on the `is_closed` flag or current time.
        Handles overnight opening and closing times (e.g., 11 PM to 4 AM).
        """
        if self.is_closed:
            return True

        current_time = localtime().time()

        if self.open_time and self.close_time:
            if self.open_time <= self.close_time:
                if not (self.open_time <= current_time <= self.close_time):
                    return True
            else:
                if not (current_time >= self.open_time or current_time <= self.close_time):
                    return True

        return False

    def is_there_enough_time(self):
        """
        Check if there is enough time for a person to join the queue based on
        the average waiting time and the time left until the queue closes.
        Handles overnight opening and closing times.
        """
        if self.is_closed:
            return False, 0
        current_datetime = localtime()
        if not self.close_time:
            return True, float('inf')
        close_datetime_naive = datetime.combine(current_datetime.date(), self.close_time)
        if self.close_time < self.open_time:
            if current_datetime.time() < self.open_time:  # Still before opening time, adjust to yesterday
                close_datetime_naive -= timedelta(days=1)
            else:  # Already past opening time, adjust to next day's close time
                close_datetime_naive += timedelta(days=1)
        close_datetime = timezone.make_aware(close_datetime_naive, current_datetime.tzinfo)
        time_left = (close_datetime - current_datetime).total_seconds() / 60
        average_wait_time = self.estimated_wait_time_per_turn * (self.get_number_waiting_now() + 1)
        return time_left >= average_wait_time, time_left

    @staticmethod
    def get_top_featured_queues():
        """Get the top 3 featured queues based on their Queue Length / Max Capacity * 100."""
        queue_ratios = []
        for queue in Queue.objects.all():
            num_participants = queue.get_number_waiting_now()
            if num_participants == 0:
                continue
            max_capacity = sum(
                resource.capacity for resource in queue.resource_set.all())
            if max_capacity == 0:
                ratio = 0
            else:
                ratio = (num_participants / max_capacity) * 100
            queue_ratios.append((queue, ratio))
        queue_ratios.sort(key=lambda x: x[1], reverse=True)
        top_3_queues = [queue for queue, ratio in queue_ratios[:3]]
        return top_3_queues

    @staticmethod
    def get_nearby_queues(user_lat, user_lon, radius_km=2):
        """Retrieve queues within a given radius of the user's location and store their distance."""
        nearby_queues = []
        for queue in Queue.objects.all():
            queue_lat, queue_lon = radians(queue.latitude), radians(
                queue.longitude)
            user_lat_rad, user_lon_rad = radians(user_lat), radians(user_lon)
            dlat = queue_lat - user_lat_rad
            dlon = queue_lon - user_lon_rad
            a = sin(dlat / 2) ** 2 + cos(user_lat_rad) * cos(queue_lat) * sin(
                dlon / 2) ** 2
            c = 2 * atan2(sqrt(a), sqrt(1 - a))
            distance_km = 6371 * c
            queue.distance_from_user = distance_km
            queue.save()
            if distance_km <= radius_km:
                nearby_queues.append(queue)
        return nearby_queues

    @property
    def formatted_distance(self):
        """Property to return the distance from user as a formatted string."""
        if self.distance_from_user is not None:
            if self.distance_from_user >= 1:
                return f"{self.distance_from_user:.1f} km"
            else:
                distance_m = self.distance_from_user * 1000
                return f"{int(distance_m)} m"
        return "Distance not available"

    def clean(self):
        if self.latitude is None or self.longitude is None:
            raise ValidationError("Latitude and Longitude cannot be null.")

        if not (-90 <= self.latitude <= 90):
            raise ValidationError("Latitude must be between -90 and 90.")

        if not (-180 <= self.longitude <= 180):
            raise ValidationError("Longitude must be between -180 and 180.")

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
        """Return a queryset of all participants in this queue. Ordered by joined_at"""
        return self.participant_set.all().order_by('joined_at')

    def update_participants_positions(self):
        participants = self.participant_set.filter(state='waiting').order_by(
            'joined_at')
        for index, participant in enumerate(participants, start=1):
            participant.position = index
            participant.save(update_fields=["position"])

    def get_number_of_participants(self) -> int:
        """Return the count of all participants in this queue, excluding cancelled and removed participants."""
        return self.participant_set.exclude(
            state__in=['cancelled', 'removed']).count()

    def get_participants_today(self) -> int:
        """Get the total number of participants added to the queue today."""
        today = timezone.now().date()
        return self.participant_set.filter(joined_at__date=today).count()

    def get_logo_url(self):
        """Get a logo URL for the queue, or return a default logo based on category."""
        if self.logo:
            return self.logo

        # Fallback to default logos based on the queue category
        default_logos = {
            'restaurant': get_s3_base_url(
                'default_images/restaurant_default_logo.png'),
            'bank': get_s3_base_url('default_images/bank_default_logo.jpg'),
            'general': get_s3_base_url(
                'default_images/general_default_logo.png'),
            'hospital': get_s3_base_url(
                'default_images/hospital_default_logo.jpg'),
            'service center': get_s3_base_url(
                'default_images/service_center_default_logo.png'),
        }
        return default_logos.get(self.category, get_s3_base_url(
            "default_images/general_default_logo.png"))

    def edit(self, name: str = None, description: str = None,
             is_closed: bool = None, status: str = None) -> None:
        """Edit the queue's name, description, or closed status."""
        if name is not None:  # Adjusted to ensure empty string validation is included
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
        return f"{settings.SITE_DOMAIN}welcome/{self.code}/"

    def get_number_of_participants_by_date(self, start_date, end_date):
        """Return the number of participants within a given date range."""
        queryset = self.participant_set.all()
        if start_date and end_date:
            queryset = self.participant_set.filter(
                joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_waiting_now(self, start_date=None, end_date=None):
        """Return the number of participants currently waiting, optionally within a date range."""
        queryset = self.participant_set.filter(state='waiting')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_completed_now(self):
        """Return the number of participant that completed the service."""
        return self.participant_set.filter(state='completed').count()

    def get_number_serving_now(self, start_date=None, end_date=None):
        """Return the number of participants currently serving, optionally within a date range."""
        queryset = self.participant_set.filter(state='serving')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_served(self, start_date=None, end_date=None):
        """Return the number of participants served, optionally within a date range."""
        queryset = self.participant_set.filter(state='completed')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_created_by_guest(self, start_date=None, end_date=None):
        """Return the number of participants joined by link, optionally within a date range."""
        queryset = self.participant_set.filter(created_by='guest')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_created_by_staff(self, start_date=None, end_date=None):
        """Return the number of participants joined by staff, optionally within a date range."""
        queryset = self.participant_set.filter(created_by='staff')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_dropoff(self, start_date=None, end_date=None):
        """Return the number of dropout participants (cancelled and removed), optionally within a date range."""
        queryset = self.participant_set.filter(
            state__in=['cancelled', 'removed'])
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_unhandled(self, start_date=None, end_date=None):
        """Return the number of unhandled participants, optionally within a date range."""
        waiting_now = self.get_number_waiting_now(start_date, end_date)
        serving_now = self.get_number_serving_now(start_date, end_date)
        return waiting_now + serving_now

    def get_guest_percentage(self, start_date=None, end_date=None):
        """Return percentage of participants joined by link, optionally within a date range."""
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        guest_count = self.get_number_created_by_guest(start_date, end_date)
        return round((guest_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_staff_percentage(self, start_date=None, end_date=None):
        """Return percentage of participants joined by staff, optionally within a date range."""
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        staff_count = self.get_number_created_by_staff(start_date, end_date)
        return round((staff_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_served_percentage(self, start_date=None, end_date=None):
        """Return percentage of participants served, optionally within a date range."""
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        served_count = self.get_number_served(start_date, end_date)
        return round((served_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_dropoff_percentage(self, start_date=None, end_date=None):
        """Return percentage of dropout participants, optionally within a date range."""
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        dropoff_count = self.get_number_dropoff(start_date, end_date)
        return round((dropoff_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_unhandled_percentage(self, start_date=None, end_date=None):
        """Return percentage of unhandled participants, optionally within a date range."""
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        unhandled_count = self.get_number_unhandled(start_date, end_date)
        return round((unhandled_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_cancelled_percentage(self, start_date=None,
                                 end_date=None) -> float:
        return self._get_substate_percentage('cancelled', start_date, end_date)

    def get_removed_percentage(self, start_date=None, end_date=None) -> float:
        return self._get_substate_percentage('removed', start_date, end_date)

    def _get_substate_percentage(self, state: str, start_date=None,
                                 end_date=None) -> float:
        dropoff_total = self.get_number_dropoff(start_date, end_date)
        queryset = self.participant_set.filter(state=state)
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return round((queryset.count() / dropoff_total) * 100,
                     2) if dropoff_total else 0

    def get_average_waiting_time(self, start_date=None, end_date=None):
        """Calculate the average waiting time for participants, optionally within a date range."""
        queryset = self.participant_set.exclude(state='waiting')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))

        waiting_times = [
            p.get_wait_time() for p in queryset if
            p.get_wait_time() is not None
        ]
        average_wait_time = math.ceil(
            sum(waiting_times) / len(waiting_times)) if waiting_times else 0
        return format_duration(average_wait_time)

    def get_max_waiting_time(self, start_date=None, end_date=None):
        """Calculate the maximum waiting time for participants, optionally within a date range."""
        queryset = self.participant_set.exclude(state='waiting')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))

        waiting_times = [
            p.get_wait_time() for p in queryset if
            p.get_wait_time() is not None
        ]
        max_wait_time = max(waiting_times) if waiting_times else 0
        return format_duration(max_wait_time)

    def get_average_service_duration(self, start_date=None, end_date=None):
        """Calculate the average service duration for participants, optionally within a date range."""
        queryset = self.participant_set.filter(state='completed')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))

        service_durations = [
            p.get_service_duration() for p in queryset if
            p.get_service_duration() is not None
        ]
        average_service_time = math.ceil(sum(service_durations) / len(
            service_durations)) if service_durations else 0
        return format_duration(average_service_time)

    def get_max_service_duration(self, start_date=None, end_date=None):
        """Get the maximum service duration for participants, optionally within a date range."""
        queryset = self.participant_set.filter(state='completed')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))

        service_durations = [
            p.get_service_duration() for p in queryset if
            p.get_service_duration() is not None
        ]
        max_service_time = max(service_durations) if service_durations else 0
        return format_duration(max_service_time)

    def record_line_length(self):
        """Records the current line length when a participant joins the queue."""
        line_length = self.participant_set.filter(state='waiting').count()
        QueueLineLength.objects.create(queue=self, line_length=line_length)

    def get_peak_line_length(self, start_date=None, end_date=None):
        """Calculate the peak line length within the specified date range."""
        queryset = QueueLineLength.objects.filter(queue=self)
        if start_date and end_date:
            queryset = queryset.filter(timestamp__range=(start_date, end_date))

        peak_record = queryset.order_by('-line_length').first()
        return peak_record.line_length if peak_record else 0

    def get_avg_line_length(self, start_date=None, end_date=None):
        """Calculate the average line length (average number of participants waiting) within a date range."""
        queryset = QueueLineLength.objects.filter(queue=self)
        if start_date and end_date:
            queryset = queryset.filter(timestamp__range=(start_date, end_date))

        total_records = queryset.count()
        if total_records == 0:
            return 0
        total_line_length = sum(record.line_length for record in queryset)
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
