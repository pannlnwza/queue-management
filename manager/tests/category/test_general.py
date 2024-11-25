from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from manager.models import Queue
from participant.models import Participant
from manager.utils.category_handler import GeneralQueueHandler
from datetime import time

class TestGeneralQueueHandler(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.handler = GeneralQueueHandler()
        self.queue = Queue.objects.create(
            name="Test general Queue",
            category="general",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=40.7128,
            longitude=-74.0060,
        )
        self.participant_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "1234567890",
            "note": "Test note",
            "queue": self.queue,
        }

    def test_create_queue(self):
        data = {"name": "New Queue", "latitude": 40.71, "longitude": 73.13}
        queue = self.handler.create_queue(data)
        self.assertEqual(queue.name, "New Queue")
        self.assertIsInstance(queue, Queue)

    def test_create_participant(self):
        participant = self.handler.create_participant(self.participant_data)
        self.assertEqual(participant.name, "John Doe")
        self.assertEqual(participant.queue, self.queue)
        self.assertEqual(participant.position, 1)

    def test_get_participant_set(self):
        participant = Participant.objects.create(**self.participant_data)
        participants = self.handler.get_participant_set(self.queue.id)
        self.assertIn(participant, participants)

    def test_get_queue_object(self):
        queue = self.handler.get_queue_object(self.queue.id)
        self.assertEqual(queue, self.queue)

    def test_complete_service(self):
        participant = Participant.objects.create(**self.participant_data, state='serving')
        self.handler.complete_service(participant)
        participant.refresh_from_db()
        self.assertEqual(participant.state, 'completed')
        self.assertIsNotNone(participant.service_completed_at)

    def test_get_template_name(self):
        template_name = self.handler.get_template_name()
        self.assertEqual(template_name, 'manager/manage_queue/manage_general.html')

    def test_add_context_attributes(self):
        context = self.handler.add_context_attributes(self.queue)
        self.assertIsNone(context)  # Assuming no additional attributes are added.

    def test_update_participant(self):
        participant = Participant.objects.create(**self.participant_data)
        updated_data = {"name": "Jane Doe", "phone": "0987654321", "notes": "Updated note"}
        self.handler.update_participant(participant, updated_data)
        participant.refresh_from_db()
        self.assertEqual(participant.name, "Jane Doe")
        self.assertEqual(participant.phone, "0987654321")
        self.assertEqual(participant.note, "Updated note")

    def test_get_participant_data(self):
        participant = Participant.objects.create(**self.participant_data)
        with patch('participant.models.Participant.get_wait_time', return_value=5):
            data = self.handler.get_participant_data(participant)
        self.assertEqual(data['name'], "John Doe")
        self.assertEqual(data['waited'], 5)
        self.assertIn('is_notified', data)

    def test_add_resource_attributes(self):
        resource_attributes = self.handler.add_resource_attributes(self.queue)
        self.assertIsNone(resource_attributes)  # Assuming no resource attributes are added.

    def test_add_resource(self):
        resource = self.handler.add_resource(self.queue)
        self.assertIsNone(resource)  # Assuming no resource creation logic.

    def test_edit_resource(self):
        resource_mock = MagicMock()
        data = {"key": "value"}
        result = self.handler.edit_resource(resource_mock, data)
        self.assertIsNone(result)  # Assuming no resource editing logic.
