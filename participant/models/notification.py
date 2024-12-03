from django.db import models
from participant.models import Participant


class Notification(models.Model):
    """Represents notification for customers."""
    queue = models.ForeignKey('manager.Queue', on_delete=models.CASCADE)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    played_sound = models.BooleanField(default=False)

    def __str__(self):
        return f"Notification for {self.participant}: {self.message}"
