import threading
from django.db import transaction
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Participant
from manager.views import logger
# Thread-local storage to avoid recursion
_thread_locals = threading.local()


def set_signal_in_progress():
    _thread_locals.in_progress = True


def get_signal_in_progress():
    return getattr(_thread_locals, 'in_progress', False)


@receiver(post_save, sender=Participant)
@receiver(post_delete, sender=Participant)
def update_queue_positions_on_save_or_delete(sender, instance, **kwargs):
    # Avoid recursion by checking if a signal is already in progress
    if get_signal_in_progress():
        return

    set_signal_in_progress()  # Set the flag to indicate signal is being handled

    try:
        logger.debug(f"Signal triggered for {sender} with participant {instance.name}")
        with transaction.atomic():
            instance.queue.update_participants_positions()
    finally:
        # Ensure to reset the flag
        _thread_locals.in_progress = False
