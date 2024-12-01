from django.contrib import messages

from django.shortcuts import redirect

from participant.models import Participant
from manager.views import logger


def participant_leave(request, participant_code):
    """Participant choose to leave the queue."""
    try:
        participant = Participant.objects.get(code=participant_code)
    except Participant.DoesNotExist:
        messages.error(request, "Couldn't find the participant in the queue.")
        logger.error(f"Couldn't find participant with {participant_code}")
        return redirect('participant:home')
    queue = participant.queue

    try:
        participant.state = 'cancelled'
        participant.save()
        messages.success(request,
                         f"We are sorry to see you leave {participant.name}. See you next time!")
        logger.info(
            f"Participant {participant.name} successfully left queue: {queue.name}.")
    except Exception as e:
        messages.error(request, f"Error removing participant: {e}")
        logger.error(
            f"Failed to delete participant {participant_code} from queue: {queue.name} code: {queue.code} ")
    return redirect('participant:welcome', queue_code=queue.code)
