import json
import time
import logging
from django.http import StreamingHttpResponse
from django.contrib.auth.decorators import login_required
from queue_manager.models import Notification

logger = logging.getLogger("queue")

@login_required
def notification_stream(request):
    """Stream unread notifications to the client."""
    def event_stream():
        last_data = None
        while True:
            try:
                notification_data = []
                notifications = Notification.objects.filter(
                    participant__user=request.user, is_read=False)
                for notification in notifications:
                    notification_data.append({
                        'id': notification.id,
                        'message': notification.message,
                        'created_at': notification.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                    })

                if notification_data != last_data:
                    last_data = notification_data
                    yield f"data: {json.dumps(notification_data)}\n\n"

            except Exception as e:
                logger.error(f"Error in event stream: {e}")
                yield f"data: {json.dumps({'error': 'Internal server error'})}\n\n"
                break

            time.sleep(1)

    return StreamingHttpResponse(event_stream(), content_type='text/event-stream')
