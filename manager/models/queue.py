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
        Determine if the queue is closed based on the `is_closed` flag or current time,
        including handling overnight opening and closing times (e.g., 11 PM to 4 AM).

        :return: A boolean indicating if the queue is closed.
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
        Determine if there is enough time for a person to join the queue, considering
        the average waiting time and the time left until the queue closes.
        This method accounts for overnight opening and closing times.

        :return: A tuple containing:
                 - A boolean indicating if there is enough time to join the queue.
                 - The time left until the queue closes in minutes (float).
                 - The average wait time for a new participant in minutes (float).
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
        average_wait_time = self.get_average_wait_time_of_new_participant()
        return time_left >= average_wait_time, time_left, average_wait_time

    def get_average_wait_time_of_new_participant(self):
        """
        Calculate and return the average wait time for a new participant about to join the queue.

        :return: A float representing the estimated average wait time for the new participant.
        """
        return self.estimated_wait_time_per_turn * (self.get_number_waiting_now() + 1)

    @staticmethod
    def get_top_featured_queues():
        """
        Retrieve the top 10 featured queues based on the Queue Length / Max Capacity * 100 ratio.

        :return: A list of the top 10 queues sorted by their queue-to-capacity ratio in descending order.
        """
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
        top_10_queues = [queue for queue, ratio in queue_ratios[:10]]
        return top_10_queues

    @staticmethod
    def get_nearby_queues(user_lat, user_lon, radius_km=2):
        """
        Retrieve queues within a specified radius of the user's location and store their distance.

        :param user_lat: Latitude of the user's location.
        :param user_lon: Longitude of the user's location.
        :param radius_km: The radius within which to find nearby queues, in kilometers (default is 2 km).
        :return: A list of queues within the specified radius from the user's location.
        """
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
        """
        Property to return the distance from the user as a formatted string.

        :return: A string representing the distance, formatted in kilometers or meters.
        """
        if self.distance_from_user is not None:
            if self.distance_from_user >= 1:
                return f"{self.distance_from_user:.1f} km"
            else:
                distance_m = self.distance_from_user * 1000
                return f"{int(distance_m)} m"
        return "Distance not available"

    def clean(self):
        """
        Validates the latitude and longitude fields to ensure they are within valid ranges.

        :raises ValidationError: If latitude or longitude are invalid or null.
        """
        if self.latitude is None or self.longitude is None:
            raise ValidationError("Latitude and Longitude cannot be null.")

        if not (-90 <= self.latitude <= 90):
            raise ValidationError("Latitude must be between -90 and 90.")

        if not (-180 <= self.longitude <= 180):
            raise ValidationError("Longitude must be between -180 and 180.")

    def has_resources(self):
        """
        Determine if the queue has resources based on its category.

        :return: A boolean indicating whether the queue has resources (category is not 'general').
        """
        return self.category != 'general'

    def get_resources_by_status(self, status):
        """
        Retrieve resources associated with the queue that match the given status.

        :param status: The status of the resources to filter by.
        :return: A queryset of resources with the specified status.
        """
        return self.resource_set.filter(
            status=status
        )

    def update_estimated_wait_time_per_turn(self, time_taken: int) -> None:
        """
        Update the estimated wait time per turn based on the time taken for a turn.

        :param time_taken: The time (in minutes) taken for the current turn.
        """
        total_time = (
                             self.estimated_wait_time_per_turn * self.completed_participants_count) + time_taken
        self.completed_participants_count += 1
        self.estimated_wait_time_per_turn = math.ceil(
            total_time / self.completed_participants_count)
        self.save()

    def calculate_average_service_duration(self, serve_time: int):
        """
        Update the average service duration based on the recent serve time.

        :param serve_time: The time (in minutes) taken to serve the most recent participant.
        """
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
        """
        Return a queryset of all participants in this queue, ordered by their join time.

        :return: A queryset of participants, ordered by the `joined_at` field.
        """
        return self.participant_set.all().order_by('joined_at')

    def update_participants_positions(self):
        """
        Update the positions of all participants in the queue who are in the 'waiting' state,
        ordered by their join time.

        :return: None
        """
        participants = self.participant_set.filter(state='waiting').order_by(
            'joined_at')
        for index, participant in enumerate(participants, start=1):
            participant.position = index
            participant.save(update_fields=["position"])

    def get_number_of_participants(self) -> int:
        """
        Return the count of all participants in this queue, excluding those with 'cancelled' or 'removed' status.

        :return: The number of active participants in the queue.
        """
        return self.participant_set.exclude(
            state__in=['cancelled', 'removed']).count()

    def get_participants_today(self) -> int:
        """
        Get the total number of participants added to the queue today.

        :return: The count of participants who joined the queue today.
        """
        today = timezone.now().date()
        return self.participant_set.filter(joined_at__date=today).count()

    def get_logo_url(self):
        """
        Get the URL for the queue's logo, or return a default logo based on the queue's category.

        :return: The URL of the queue's logo or a default logo URL.
        """
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
        """
        Edit the queue's name, description, closed status, or current status.

        :param name: The new name for the queue (optional).
        :param description: The new description for the queue (optional).
        :param is_closed: The new closed status for the queue (optional).
        :param status: The new status for the queue (optional).
        :raises ValueError: If the name is not between 1 and 255 characters.
        """
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
        Fetch an available resource with enough capacity that is currently empty.

        :param required_capacity: The required capacity for the resource (default is 1).
        :return: The first available resource that meets the capacity requirement, or None if no such resource is found.
        """
        return self.resource_set.filter(
            status='available',
            capacity__gte=required_capacity
        ).first()

    def get_join_link(self):
        """
        Returns the full URL to the welcome page for this queue.

        :return: A string representing the URL to the queue's welcome page.
        """
        return f"{settings.SITE_DOMAIN}welcome/{self.code}/"

    def get_number_of_participants_by_date(self, start_date, end_date):
        """
        Return the number of participants within a given date range.

        :param start_date: The start date for the range.
        :param end_date: The end date for the range.
        :return: The count of participants who joined within the specified date range.
        """
        queryset = self.participant_set.all()
        if start_date and end_date:
            queryset = self.participant_set.filter(
                joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_waiting_now(self, start_date=None, end_date=None):
        """
        Return the number of participants currently waiting, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The count of participants who are currently waiting.
        """
        queryset = self.participant_set.filter(state='waiting')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_completed_now(self):
        """
        Return the number of participants who have completed the service.

        :return: The count of participants with the 'completed' status.
        """
        return self.participant_set.filter(state='completed').count()

    def get_number_serving_now(self, start_date=None, end_date=None):
        """
        Return the number of participants currently serving, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The count of participants with the 'serving' status.
        """
        queryset = self.participant_set.filter(state='serving')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_served(self, start_date=None, end_date=None):
        """
        Return the number of participants served, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The count of participants with the 'completed' status.
        """
        queryset = self.participant_set.filter(state='completed')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_created_by_guest(self, start_date=None, end_date=None):
        """
        Return the number of participants who joined via a link, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The count of participants who joined as 'guest'.
        """
        queryset = self.participant_set.filter(created_by='guest')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_created_by_staff(self, start_date=None, end_date=None):
        """
        Return the number of participants who joined via staff, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The count of participants who joined as 'staff'.
        """
        queryset = self.participant_set.filter(created_by='staff')
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_dropoff(self, start_date=None, end_date=None):
        """
        Return the number of participants who dropped off (cancelled or no-show), optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The count of participants who dropped off.
        """
        queryset = self.participant_set.filter(
            state__in=['cancelled', 'no_show'])
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return queryset.count()

    def get_number_unhandled(self, start_date=None, end_date=None):
        """
        Return the number of unhandled participants (waiting or serving), optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The total count of unhandled participants (waiting + serving).
        """
        waiting_now = self.get_number_waiting_now(start_date, end_date)
        serving_now = self.get_number_serving_now(start_date, end_date)
        return waiting_now + serving_now

    def get_guest_percentage(self, start_date=None, end_date=None):
        """
        Return the percentage of participants who joined via link, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants who joined as guests.
        """
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        guest_count = self.get_number_created_by_guest(start_date, end_date)
        return round((guest_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_staff_percentage(self, start_date=None, end_date=None):
        """
        Return the percentage of participants who joined via staff, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants who joined as staff.
        """
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        staff_count = self.get_number_created_by_staff(start_date, end_date)
        return round((staff_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_served_percentage(self, start_date=None, end_date=None):
        """
        Return the percentage of participants who have been served, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants who have been served.
        """
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        served_count = self.get_number_served(start_date, end_date)
        return round((served_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_dropoff_percentage(self, start_date=None, end_date=None):
        """
        Return the percentage of participants who dropped off (cancelled or no-show), optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants who dropped off.
        """
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        dropoff_count = self.get_number_dropoff(start_date, end_date)
        return round((dropoff_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_unhandled_percentage(self, start_date=None, end_date=None):
        """
        Return the percentage of unhandled participants (waiting or serving), optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of unhandled participants.
        """
        num_participants = self.get_number_of_participants_by_date(start_date,
                                                                   end_date)
        unhandled_count = self.get_number_unhandled(start_date, end_date)
        return round((unhandled_count / num_participants) * 100,
                     2) if num_participants else 0

    def get_cancelled_percentage(self, start_date=None, end_date=None) -> float:
        """
        Calculate the percentage of participants in the 'cancelled' state, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants with the 'cancelled' state.
        """
        return self._get_substate_percentage('cancelled', start_date, end_date)

    def get_no_show_percentage(self, start_date=None, end_date=None) -> float:
        """
        Calculate the percentage of participants in the 'no_show' state, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants with the 'no_show' state.
        """
        return self._get_substate_percentage('no_show', start_date, end_date)

    def _get_substate_percentage(self, state: str, start_date=None, end_date=None) -> float:
        """
        Compute the percentage of participants in a specific state (e.g., 'cancelled', 'no_show')
        within the given date range.

        :param state: The state to filter participants by (e.g., 'cancelled', 'no_show').
        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The percentage of participants in the specified state.
        """
        dropoff_total = self.get_number_dropoff(start_date, end_date)
        queryset = self.participant_set.filter(state=state)
        if start_date and end_date:
            queryset = queryset.filter(joined_at__range=(start_date, end_date))
        return round((queryset.count() / dropoff_total) * 100,
                     2) if dropoff_total else 0

    def get_average_waiting_time(self, start_date=None, end_date=None):
        """
        Calculate the average waiting time for participants, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The average waiting time formatted as a string.
        """
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
        """
        Calculate the maximum waiting time for participants, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The maximum waiting time formatted as a string.
        """
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
        """
        Calculate the average service duration for participants, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The average service duration formatted as a string.
        """
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
        """
        Get the maximum service duration for participants, optionally within a date range.

        :param start_date: The start date for the filter (optional).
        :param end_date: The end date for the filter (optional).
        :return: The maximum service duration formatted as a string.
        """
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
        """
        Records the current line length when a participant joins the queue.

        :return: None
        """
        line_length = self.participant_set.filter(state='waiting').count()
        QueueLineLength.objects.create(queue=self, line_length=line_length)

    def get_peak_line_length(self, start_date=None, end_date=None):
        """
        Calculate the peak line length within the specified date range.

        :param start_date: The start date for filtering (optional).
        :param end_date: The end date for filtering (optional).
        :return: The peak line length, or 0 if no records are found.
        """
        queryset = QueueLineLength.objects.filter(queue=self)
        if start_date and end_date:
            queryset = queryset.filter(timestamp__range=(start_date, end_date))

        peak_record = queryset.order_by('-line_length').first()
        return peak_record.line_length if peak_record else 0

    def get_avg_line_length(self, start_date=None, end_date=None):
        """
        Calculate the average line length (average number of participants waiting) within a date range.

        :param start_date: The start date for filtering (optional).
        :param end_date: The end date for filtering (optional).
        :return: The average line length, or 0 if no records are found.
        """
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
