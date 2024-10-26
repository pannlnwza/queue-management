import json
import logging
import time

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from queue_manager.models import Queue

logger = logging.getLogger('queue')


@login_required
def queue_stream(request):
    """Stream queue data updates to the client."""

    def event_stream():
        last_data = None
        while True:
            try:
                queue_data = []
                users_queues = Queue.objects.filter(participant__user=request.user)

                for queue in users_queues:
                    user_position = queue.participant_set.filter(user=request.user).first().position
                    queue_data.append({
                        'id': queue.id,
                        'name': queue.name,
                        'position': user_position,
                        'participant_count': queue.participant_set.count(),
                        'status': queue.get_status_display(),
                    })

                if queue_data != last_data:
                    last_data = queue_data
                    yield f"data: {json.dumps(queue_data)}\n\n"

            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
                break
            time.sleep(1)  # check for changes every second

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')


@login_required
def queue_dashboard_stream(request, queue_id):
    """Stream queue data updates to the queue creator for a specific queue."""
    queue = get_object_or_404(Queue, id=queue_id)

    def event_stream():
        last_data = None
        while True:
            try:
                participants = [
                    {
                        'id': participant.id,
                        'username': participant.user.username if participant.user else "-",
                        'position': participant.position,
                        'joined_at': timezone.localtime(participant.joined_at).strftime(
                            '%d-%m-%Y %H:%M:%S') if participant.joined_at else "-",
                        'estimated_wait_time': queue.estimated_wait_time,
                        'queue_code': participant.queue_code
                    }
                    for participant in queue.participant_set.all()
                ]

                queue_data = {
                    'id': queue.id,
                    'name': queue.name,
                    'current_queue_length': queue.participant_set.count(),
                    'estimated_wait_time': queue.estimated_wait_time,
                    'participants_today': queue.get_participants_today(),
                    'participants': participants,
                }

                if queue_data != last_data:
                    last_data = queue_data
                    yield f"data: {json.dumps(queue_data)}\n\n"

            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
                break
            time.sleep(5)

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
