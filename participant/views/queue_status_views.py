import asyncio
import json
import threading
from queue import Queue as ThreadSafeQueue
from django.shortcuts import get_object_or_404
from participant.models import Participant, Notification
from manager.utils.category_handler import CategoryHandlerFactory
from manager.utils.aws_s3_storage import get_s3_base_url
from django.views import generic
from django.utils import timezone
from django.http import StreamingHttpResponse
from asgiref.sync import sync_to_async


class QueueStatusView(generic.TemplateView):
    template_name = 'participant/status.html'

    def get_context_data(self, **kwargs):
        """Add the queue and participants context to template."""
        context = super().get_context_data(**kwargs)
        # look for 'participant_code' in the url
        participant_code = kwargs['participant_code']
        # get the participant
        participant = get_object_or_404(Participant, code=participant_code)
        # get the queue
        queue = participant.queue
        # add in context data
        context['queue'] = queue
        context['participant'] = participant
        # Get the list of all participants in the same queue
        participants_in_queue = queue.participant_set.all().order_by(
            'joined_at')
        context['participants_in_queue'] = participants_in_queue
        context['participant_sound'] = get_s3_base_url(
            "announcements/notification.mp3")
        return context


def sse_queue_status(request, participant_code):
    """Server-sent Events endpoint to stream the queue status."""

    def event_stream():
        """Synchronous generator to stream events."""
        while True:
            try:
                message = event_queue.get()
                if message is None:  # Sentinel value to terminate the stream
                    break
                yield f"data: {message}\n\n"
            except Exception as e:
                print("Error in synchronous event stream:", e)
                break

    async def async_event_producer():
        """Asynchronous task to fetch and send data."""
        last_data = None
        while True:
            try:
                # Wrap all sync database or blocking operations in `sync_to_async`
                participant, queue, handler = await fetch_participant_and_queue()

                # Fetch participant data
                participant_data = await sync_to_async(
                    handler.get_participant_data)(participant)

                # Fetch notifications
                notifications = await fetch_notifications(participant)

                # Mark notifications as played
                notification_ids = [notif['id'] for notif in notifications if
                                    not notif['played_sound']]
                if notification_ids:
                    await mark_notifications_played(notification_ids)

                participant_data['notification_set'] = notifications

                if last_data != participant_data:
                    message = json.dumps(participant_data)
                    event_queue.put(message)
                    last_data = participant_data

                # await asyncio.sleep(15)
            except Exception as e:
                print("Error in async event producer:", e)
                break
        event_queue.put(None)  # Send sentinel value to stop the stream

    @sync_to_async
    def fetch_participant_and_queue():
        """Fetch participant and queue details synchronously."""
        participant_instance = get_object_or_404(Participant,
                                                 code=participant_code)
        queue = participant_instance.queue
        handler = CategoryHandlerFactory.get_handler(queue.category)
        participant = handler.get_participant_set(queue_id=queue.id).get(
            code=participant_code)
        return participant, queue, handler

    @sync_to_async
    def fetch_notifications(participant):
        """Fetch notifications for the participant."""
        notifications = Notification.objects.filter(participant=participant)
        return [
            {
                'message': notif.message,
                'created_at': timezone.localtime(notif.created_at).strftime(
                    "%Y-%m-%d %H:%M:%S"),
                'is_read': notif.is_read,
                'played_sound': notif.played_sound,
                'id': notif.id,
            }
            for notif in notifications
        ]

    @sync_to_async
    def mark_notifications_played(notification_ids):
        """Mark notifications as played."""
        Notification.objects.filter(id__in=notification_ids).update(
            played_sound=True)

    # Set up a thread-safe queue to bridge async and sync contexts
    event_queue = ThreadSafeQueue()

    # Start the async event producer in a separate thread
    producer_thread = threading.Thread(
        target=lambda: asyncio.run(async_event_producer()))
    producer_thread.start()

    # Return the StreamingHttpResponse that consumes the sync iterator
    return StreamingHttpResponse(event_stream(),
                                 content_type="text/event-stream")
