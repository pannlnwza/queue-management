import json
import asyncio
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.shortcuts import get_object_or_404
from django.utils import timezone
from .models import Participant, Notification
from manager.utils.category_handler import CategoryHandlerFactory

class QueueStatusConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Extract participant code from the URL route
        self.participant_code = self.scope['url_route']['kwargs']['participant_code']
        self.queue_group_name = f"queue_{self.participant_code}"

        # Add the WebSocket connection to the group
        await self.channel_layer.group_add(
            self.queue_group_name,
            self.channel_name
        )

        # Accept the WebSocket connection
        await self.accept()
        print(f"WebSocket connected: {self.participant_code}")

        # Start sending data
        self.last_data = None
        self.keep_streaming = True
        self.loop_task = asyncio.create_task(self.send_participant_updates())

    async def disconnect(self, close_code):
        # Remove the WebSocket connection from the group
        await self.channel_layer.group_discard(
            self.queue_group_name,
            self.channel_name
        )
        print(f"WebSocket disconnected: {self.participant_code}")

        # Stop the loop for sending updates
        self.keep_streaming = False
        if hasattr(self, 'loop_task'):
            self.loop_task.cancel()

    async def send_participant_updates(self):
        """Continuously fetch and send participant updates."""
        while self.keep_streaming:
            try:
                print("Fetching participant and queue details...")

                # Fetch participant and queue details
                participant, queue, handler = await self.fetch_participant_and_queue()

                # Fetch participant data
                participant_data = await sync_to_async(handler.get_participant_data)(participant)

                # Fetch notifications
                notifications = await self.fetch_notifications(participant)

                # Mark notifications as played
                notification_ids = [notif['id'] for notif in notifications if not notif['played_sound']]
                if notification_ids:
                    await self.mark_notifications_played(notification_ids)

                participant_data['notification_set'] = notifications

                # Send the data only if it has changed
                if self.last_data != participant_data:
                    self.last_data = participant_data
                    print(f"Sending data to WebSocket: {participant_data}")
                    await self.send(json.dumps(participant_data))

                # Wait for the next update
                await asyncio.sleep(5)

            except Exception as e:
                print(f"Error in send_participant_updates: {e}")
                break

    @sync_to_async
    def fetch_participant_and_queue(self):
        """Fetch participant and queue details synchronously."""
        participant_instance = get_object_or_404(Participant, code=self.participant_code)
        queue = participant_instance.queue
        handler = CategoryHandlerFactory.get_handler(queue.category)
        participant = handler.get_participant_set(queue_id=queue.id).get(code=self.participant_code)
        return participant, queue, handler

    @sync_to_async
    def fetch_notifications(self, participant):
        """Fetch notifications for the participant."""
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
        """Mark notifications as played."""
        Notification.objects.filter(id__in=notification_ids).update(played_sound=True)
