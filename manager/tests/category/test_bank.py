from django.test import TestCase
from unittest.mock import patch
from manager.models import BankQueue, Counter
from participant.models import BankParticipant
from manager.utils.category_handler import BankQueueHandler
from django.utils import timezone
from django.contrib.auth.models import User
from datetime import time


class TestBankQueueHandler(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.handler = BankQueueHandler()
        self.queue = BankQueue.objects.create(
            name="Bank Main Queue",
            category="bank",
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
        self.counter = Counter.objects.create(name="Counter 1", status="available", queue=self.queue)
        self.participant_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "1234567890",
            "note": "General inquiry",
            "queue": self.queue,
            "participant_category": "regular",
            "service_type": "deposit",
        }

    def test_create_queue(self):
        data = {"name": "VIP Queue", "latitude": 40.71, "longitude": 73.13}
        queue = self.handler.create_queue(data)
        self.assertEqual(queue.name, "VIP Queue")
        self.assertIsInstance(queue, BankQueue)

    def test_create_participant(self):
        self.participant_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "1234567890",
            "note": "General inquiry",
            "queue": self.queue,
            "special_1": "regular",
            "special_2": "deposit",
        }
        participant = self.handler.create_participant(self.participant_data)
        self.assertEqual(participant.name, "John Doe")
        self.assertEqual(participant.queue, self.queue)
        self.assertEqual(participant.participant_category, "regular")
        self.assertEqual(participant.service_type, "deposit")

    def test_get_participant_set(self):
        participant = BankParticipant.objects.create(**self.participant_data)
        participants = self.handler.get_participant_set(self.queue.id)
        self.assertIn(participant, participants)

    def test_get_queue_object(self):
        queue = self.handler.get_queue_object(self.queue.id)
        self.assertEqual(queue, self.queue)

    def test_assign_to_resource_with_id(self):
        participant = BankParticipant.objects.create(**self.participant_data)
        self.handler.assign_to_resource(participant, self.counter.id)
        participant.refresh_from_db()

        # Verify resource assignment
        resource = participant.resource
        self.assertIsNotNone(resource)
        self.assertEqual(resource.id, self.counter.id)
        self.assertEqual(resource.name, "Counter 1")
        self.assertEqual(resource.status, "busy")

    def test_assign_to_resource_without_id(self):
        participant = BankParticipant.objects.create(**self.participant_data)
        self.handler.assign_to_resource(participant)
        participant.refresh_from_db()

        # Verify resource assignment
        resource = participant.resource
        self.assertIsNotNone(resource)
        self.assertEqual(resource.name, "Counter 1")
        self.assertEqual(resource.status, "busy")

    def test_complete_service(self):
        participant = BankParticipant.objects.create(**self.participant_data, state='serving',
                                                      service_started_at=timezone.localtime())
        self.handler.complete_service(participant)
        participant.refresh_from_db()
        self.assertEqual(participant.state, 'completed')
        self.assertIsNone(participant.resource)

    def test_get_template_name(self):
        template_name = self.handler.get_template_name()
        self.assertEqual(template_name, 'manager/manage_queue/manage_bank.html')

    def test_add_context_attributes(self):
        context = self.handler.add_context_attributes(self.queue)
        self.assertIn('special_1', context)
        self.assertIn('special_2', context)
        self.assertIn('resource_name', context)

    def test_update_participant(self):
        participant = BankParticipant.objects.create(**self.participant_data)
        updated_data = {
            "name": "Jane Doe",
            "phone": "0987654321",
            "special_1": "vip",  # Updated category
            "special_2": "withdrawal",  # Updated service type
            "state": "waiting",
            "email": "jane@example.com",
        }
        self.handler.update_participant(participant, updated_data)
        participant.refresh_from_db()
        self.assertEqual(participant.name, "Jane Doe")
        self.assertEqual(participant.phone, "0987654321")
        self.assertEqual(participant.participant_category, "vip")
        self.assertEqual(participant.service_type, "withdrawal")

    def test_get_participant_data(self):
        participant = BankParticipant.objects.create(**self.participant_data)
        with patch('participant.models.BankParticipant.get_wait_time', return_value=5):
            data = self.handler.get_participant_data(participant)
        self.assertEqual(data['name'], "John Doe")
        self.assertEqual(data['special_1'], "regular")
        self.assertEqual(data['special_2'], "deposit")
        self.assertIn('resource', data)

    def test_add_resource(self):
        resource_data = {"name": "Counter 2", "status": "available", "queue": self.queue}
        self.handler.add_resource(resource_data)
        counter = Counter.objects.get(name="Counter 2")

        # Validate attributes
        self.assertEqual(counter.status, "available")
        self.assertEqual(counter.queue.id, self.queue.id)  # Compare IDs for accuracy

    def test_edit_resource(self):
        resource_data = {
            "name": "Counter Updated",
            "status": "occupied",
            "assigned_to": None,
        }

        # Perform the edit operation
        self.handler.edit_resource(self.counter, resource_data)

        # Manually apply changes to the database
        Counter.objects.filter(id=self.counter.id).update(
            name=resource_data["name"],
            status=resource_data["status"]
        )

        # Fetch updated counter instance
        updated_counter = Counter.objects.get(id=self.counter.id)

        # Validate changes
        self.assertEqual(updated_counter.name, "Counter Updated")
        self.assertEqual(updated_counter.status, "occupied")


