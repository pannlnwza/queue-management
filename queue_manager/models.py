from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    """
    Extends the built-in User model with additional profile information.

    This model maintains a one-to-one relationship with the User model,
    allowing for storage of supplementary user data such as a biography
    and birthdate.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    birth_date = models.DateField(null=True, blank=True)


class Queue(models.Model):
    """
    Represents a queue that users can create and manage.

    Each queue is owned by a user and can have multiple participants.
    It stores basic information about the queue such as its name,
    description, owner, and creation time.
    """
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name='owned_queues')
    created_at = models.DateTimeField(auto_now_add=True)


class Participant(models.Model):
    """
    Represents a user's participation in a specific queue.

    This model links a user to a queue they've joined, tracking their
    position, join time, and current status within the queue. It ensures
    that a user can only join a specific queue once.
    """
    STATUS_CHOICES = [
        ('WAITING', 'Waiting'),
        ('ACTIVE', 'Active'),
        ('SERVED', 'Served'),
        ('LEFT', 'Left'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='participations')
    queue = models.ForeignKey(Queue, on_delete=models.CASCADE, related_name='participants')
    position = models.PositiveIntegerField()
    joined_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='WAITING')

    class Meta:
        unique_together = ['user', 'queue']
        ordering = ['position']
