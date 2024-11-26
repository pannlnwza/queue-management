import json
import asyncio
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps  # Import for lazy model loading
from django.utils import timezone
from manager.utils.category_handler import CategoryHandlerFactory
import logging

logger = logging.getLogger('queue')

class QueueStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.participant_code = self.scope['url_route']['kwargs']['participant_code']
        self.queue_group_name = f"queue_{self.participant_code}"

        await self.channel_layer.group_add(
            self.queue_group_name,
            self.channel_name
        )

        await self.accept()
        self.last_data = None
        self.keep_streaming = True
        self.loop_task = asyncio.create_task(self.send_participant_updates())

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.queue_group_name,
            self.channel_name
        )
        self.keep_streaming = False
        if hasattr(self, 'loop_task'):
            self.loop_task.cancel()

    async def send_participant_updates(self):
        while self.keep_streaming:
            try:
                participant, queue, handler = await self.fetch_participant_and_queue()

                participant_data = await sync_to_async(handler.get_participant_data)(participant)
                notifications = await self.fetch_notifications(participant)

                notification_ids = [notif['id'] for notif in notifications if not notif['played_sound']]
                if notification_ids:
                    await self.mark_notifications_played(notification_ids)

                participant_data['notification_set'] = notifications

                if self.last_data != participant_data:
                    self.last_data = participant_data
                    await self.send(json.dumps(participant_data))

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in send_participant_updates: {e}")
                break

    @sync_to_async
    def fetch_participant_and_queue(self):
        Participant = apps.get_model('participant', 'Participant')  # Lazy load
        participant_instance = Participant.objects.get(code=self.participant_code)
        queue = participant_instance.queue
        handler = CategoryHandlerFactory.get_handler(queue.category)
        participant = handler.get_participant_set(queue_id=queue.id).get(code=self.participant_code)
        return participant, queue, handler

    @sync_to_async
    def fetch_notifications(self, participant):
        Notification = apps.get_model('participant', 'Notification')  # Lazy load
        notifications = Notification.objects.filter(participant=participant)
        return [
            {
                'id': notif.id,
                'message': notif.message,
                'created_at': timezone.localtime(notif.created_at).strftime("%Y-%m-%d %H:%M:%S"),
                'is_read': notif.is_read,
                'played_sound': notif.played_sound,
            }
            for notif in notifications
        ]

    @sync_to_async
    def mark_notifications_played(self, notification_ids):
        Notification = apps.get_model('participant', 'Notification')  # Lazy load
        Notification.objects.filter(id__in=notification_ids).update(played_sound=True)
