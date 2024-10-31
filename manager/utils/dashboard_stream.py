import json
import time

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from participant.utils.data_stream import logger
from manager.models import Queue


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
                        'estimated_wait_time': participant.calculate_estimated_wait_time(),
                        'queue_code': participant.queue_code
                    }
                    for participant in queue.participant_set.all()
                ]

                queue_data = {
                    'id': queue.id,
                    'name': queue.name,
                    'current_queue_length': queue.participant_set.count(),
                    'estimated_wait_time_per_turn': queue.estimated_wait_time_per_turn,
                    'participants_today': queue.get_participants_today(),
                    'participants': participants,
                    'completed_participants': queue.completed_participants_count
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
