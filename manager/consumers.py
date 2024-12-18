import asyncio
import json
import logging
from asgiref.sync import sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer
from django.apps import apps

logger = logging.getLogger('queue')


class QueueDisplayConsumer(AsyncWebsocketConsumer):
    """
    A WebSocket consumer for managing the real-time queue updates for a specific queue.
    """
    async def connect(self):
        """
        Establishes the WebSocket connection for the queue manager.

        :return: Accepts the WebSocket connection.
        """
        self.queue_id = self.scope['url_route']['kwargs']['queue_id']
        self.manager_group_name = f"manager_{self.queue_id}"
        await self.channel_layer.group_add(
            self.manager_group_name,
            self.channel_name
        )

        await self.accept()

        self.keep_streaming = True
        self.loop_task = asyncio.create_task(self.send_queue_updates())

    async def disconnect(self, close_code):
        """
        Closes the WebSocket connection and stops the streaming of queue updates.

        :param close_code: The code indicating why the connection was closed.
        """
        await self.channel_layer.group_discard(
            self.manager_group_name,
            self.channel_name
        )
        self.keep_streaming = False
        if hasattr(self, 'loop_task'):
            self.loop_task.cancel()

    async def send_queue_updates(self):
        """
        Periodically sends updates about the queue status to the WebSocket connection.

        This method fetches the current state of the queue, including the list of participants,
        the participant being called, and the next in line, and sends this data to the client
        every 5 seconds. It stops when an error occurs or when the connection is closed.

        :return: None
        """
        while self.keep_streaming:
            try:
                participants, calling, next_in_line = await self.fetch_queue_participants_and_status()

                data = {
                    'participants': participants,
                    'calling': calling,
                    'next_in_line': next_in_line,
                }
                await self.send(json.dumps(data))

                await asyncio.sleep(5)

            except Exception as e:
                logger.error(f"Error in send_queue_updates: {e}")
                break

    @sync_to_async
    def fetch_queue_participants_and_status(self):
        """
        Fetches the current list of participants and their status for the queue.

        :return: A tuple containing participant data, the calling participant's number, and the next
                 in line's number.
        """
        Participant = apps.get_model('participant', 'Participant')
        calling = Participant.objects.filter(queue_id=self.queue_id, is_notified=True).order_by(
            '-notification__created_at').first()
        calling_number = calling.number if calling else None

        next_in_line = Participant.objects.filter(queue_id=self.queue_id, state='waiting').exclude(is_notified=True).order_by(
            'position').first()
        next_in_line_number = next_in_line.number if next_in_line else "-"
        participants = (
            Participant.objects.filter(queue_id=self.queue_id, state='waiting')
            .exclude(pk=calling.pk if calling else None)
            .order_by('joined_at')
        )

        participant_data = [
            {
                'number': participant.number,
                'wait_time': participant.get_wait_time(),
                'estimated_wait_time': participant.calculate_estimated_wait_time(),
                'is_notified': participant.is_notified,
            }
            for participant in participants
        ]

        return participant_data, calling_number, next_in_line_number