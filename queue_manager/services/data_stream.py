import json
import logging
import time

from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone

from queue_manager.models import Queue, Notification

logger = logging.getLogger('queue')


@login_required
def data_stream(request):
    """Stream unread notifications and queue data updates to the client."""

    def event_stream():
        last_notification_data = None
        last_queue_data = None
        while True:
            try:
                notifications = Notification.objects.filter(
                    participant__user=request.user, is_read=False
                ).order_by('created_at')

                notification_data = [
                    {
                        'id': notification.id,
                        'message': notification.message,
                        'queue_name': notification.queue.name,
                        'created_at': timezone.localtime(notification.created_at).strftime('%Y-%m-%d %H:%M:%S'),
                    }
                    for notification in notifications
                ]

                queue_data = []
                users_queues = Queue.objects.filter(participant__user=request.user)

                for queue in users_queues:
                    queue_data.append({
                        'id': queue.id,
                        'name': queue.name,
                        'position': queue.participant_set.filter(user=request.user).first().position,
                        'estimated_wait_time': queue.participant_set.filter(user=request.user).first().calculate_estimated_wait_time(),
                        'participant_count': queue.participant_set.count(),
                        'status': queue.status.title(),
                    })

                if notification_data != last_notification_data or queue_data != last_queue_data:
                    last_notification_data = notification_data
                    last_queue_data = queue_data

                    combined_data = {
                        'notifications': notification_data,
                        'queues': queue_data,
                    }

                    yield f"data: {json.dumps(combined_data)}\n\n"

            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
                break

            time.sleep(5)

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
