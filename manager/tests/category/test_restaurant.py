from django.test import TestCase
from unittest.mock import patch, MagicMock
from django.contrib.auth.models import User
from manager.models import RestaurantQueue, Table, Queue
from participant.models import RestaurantParticipant
from manager.utils.category_handler import RestaurantQueueHandler
from django.utils import timezone
from datetime import time


class TestRestaurantQueueHandler(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.handler = RestaurantQueueHandler()
        self.queue = RestaurantQueue.objects.create(
            name="Test Queue",
            category="restaurant",
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
        self.table = Table.objects.create(name="Table 1", capacity=4, status="available", queue=self.queue)
        self.participant_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "1234567890",
            "note": "Test note",
            "queue": self.queue,
            "party_size": 4,
            "service_type": "dine_in",
        }

    def test_create_queue(self):
        data = {"name": "New Restaurant Queue", "latitude": 40.71, "longitude": 73.13}
        queue = self.handler.create_queue(data)
        self.assertEqual(queue.name, "New Restaurant Queue")
        self.assertIsInstance(queue, RestaurantQueue)

    def test_create_participant(self):
        self.participant_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "1234567890",
            "note": "Test note",
            "queue": self.queue,
            "special_1": 4,
            "special_2": "dine_in",
        }
        participant = self.handler.create_participant(self.participant_data)
        self.assertEqual(participant.name, "John Doe")
        self.assertEqual(participant.queue, self.queue)
        self.assertEqual(participant.party_size, 4)
        self.assertEqual(participant.service_type, "dine_in")
        self.assertEqual(participant.position, 1)

    def test_get_participant_set(self):
        participant = RestaurantParticipant.objects.create(**self.participant_data)
        participants = self.handler.get_participant_set(self.queue.id)
        self.assertIn(participant, participants)

    def test_get_queue_object(self):
        queue = self.handler.get_queue_object(self.queue.id)
        self.assertEqual(queue, self.queue)

    def test_assign_to_resource_with_id(self):
        participant = RestaurantParticipant.objects.create(**self.participant_data)
        self.handler.assign_to_resource(participant, self.table.id)
        participant.refresh_from_db()

        # Fetch the updated resource and compare attributes
        resource = participant.resource
        self.assertIsNotNone(resource)  # Ensure resource is assigned
        self.assertEqual(resource.id, self.table.id)  # Compare IDs
        self.assertEqual(resource.name, self.table.name)  # Compare names
        self.assertEqual(resource.status, "busy")  # Ensure status is updated

    def test_assign_to_resource_without_id(self):
        participant = RestaurantParticipant.objects.create(**self.participant_data)
        self.handler.assign_to_resource(participant)
        participant.refresh_from_db()

        # Fetch the updated resource and compare attributes
        resource = participant.resource
        self.assertIsNotNone(resource)  # Ensure resource is assigned
        self.assertEqual(resource.id, self.table.id)  # Compare IDs
        self.assertEqual(resource.name, self.table.name)  # Compare names
        self.assertEqual(resource.status, "busy")  # Ensure status is updated

    def test_complete_service(self):
        participant = RestaurantParticipant.objects.create(**self.participant_data, state='serving',
                                                            service_started_at=timezone.localtime())
        self.handler.complete_service(participant)
        participant.refresh_from_db()
        self.assertEqual(participant.state, 'completed')
        self.assertIsNone(participant.resource)

    def test_get_template_name(self):
        template_name = self.handler.get_template_name()
        self.assertEqual(template_name, 'manager/manage_queue/manage_unique_category.html')

    def test_add_context_attributes(self):
        context = self.handler.add_context_attributes(self.queue)
        self.assertIn('special_1', context)
        self.assertIn('special_2', context)
        self.assertIn('resource_name', context)

    def test_update_participant(self):
        participant = RestaurantParticipant.objects.create(**self.participant_data)
        updated_data = {
            "name": "Jane Doe",
            "phone": "0987654321",
            "special_1": 2,  # Updated party size
            "special_2": "takeout",  # Updated service type
            "state": "waiting",
            "email": "jane@example.com",
        }
        self.handler.update_participant(participant, updated_data)
        participant.refresh_from_db()
        self.assertEqual(participant.name, "Jane Doe")
        self.assertEqual(participant.phone, "0987654321")
        self.assertEqual(participant.party_size, 2)
        self.assertEqual(participant.service_type, "takeout")

    def test_get_participant_data(self):
        participant = RestaurantParticipant.objects.create(**self.participant_data)
        with patch('participant.models.RestaurantParticipant.get_wait_time', return_value=5):
            data = self.handler.get_participant_data(participant)
        self.assertEqual(data['name'], "John Doe")
        self.assertEqual(data['special_1'], "4 people")
        self.assertIn('resource', data)

    def test_add_resource(self):
        resource_data = {"name": "Table 2", "special": 6, "status": "available", "queue": self.queue}
        self.handler.add_resource(resource_data)
        table = Table.objects.get(name="Table 2")
        self.assertEqual(table.capacity, 6)
        self.assertEqual(table.status, "available")

    def test_edit_resource(self):
        resource_data = {"name": "Updated Table", "special": 8, "status": "occupied"}
        self.handler.edit_resource(self.table, resource_data)
        self.table.refresh_from_db()
        self.assertEqual(self.table.name, "Updated Table")
        self.assertEqual(self.table.capacity, 8)
        self.assertEqual(self.table.status, "occupied")
