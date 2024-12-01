import asyncio
import json
import logging

from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps

from participant.models import Participant

logger = logging.getLogger('queue')

class QueueDisplayConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.queue_id = self.scope['url_route']['kwargs']['queue_id']
        self.manager_group_name = f"manager_{self.queue_id}"

        # Add the manager to the queue group
        await self.channel_layer.group_add(
            self.manager_group_name,
            self.channel_name
        )

        await self.accept()

        # Start streaming updates to the manager
        self.keep_streaming = True
        self.loop_task = asyncio.create_task(self.send_queue_updates())

    async def disconnect(self, close_code):
        # Remove the manager from the group
        await self.channel_layer.group_discard(
            self.manager_group_name,
            self.channel_name
        )
        self.keep_streaming = False
        if hasattr(self, 'loop_task'):
            self.loop_task.cancel()

    async def send_queue_updates(self):
        while self.keep_streaming:
            try:


                # Fetch the calling and next in line participant details
                participants, calling, next_in_line = await self.fetch_queue_participants_and_status()

                # Prepare the data to send
                data = {
                    'participants': participants,
                    'calling': calling,
                    'next_in_line': next_in_line,
                }

                # Send the updates to the manager WebSocket
                await self.send(json.dumps(data))

                # Update every 5 seconds
                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in send_queue_updates: {e}")
                break

    @sync_to_async
    def fetch_queue_participants_and_status(self):
        Participant = apps.get_model('participant', 'Participant')
        participants = Participant.objects.filter(queue_id=self.queue_id, state='waiting').order_by('position')[1:10]
        calling = Participant.objects.filter(queue_id=self.queue_id, is_notified=True).order_by(
            '-notification__created_at').first()
        calling_number = calling.number if calling else None

        next_in_line = Participant.objects.filter(queue_id=self.queue_id).exclude(is_notified=True).order_by(
            'position').first()
        next_in_line_number = next_in_line.number if next_in_line else None

        participant_data = [
            {
                'number': participant.number,
                'wait_time': participant.get_wait_time(),
                'estimated_wait_time': participant.calculate_estimated_wait_time()
            }
            for participant in participants
        ]

        return participant_data, calling_number, next_in_line_number