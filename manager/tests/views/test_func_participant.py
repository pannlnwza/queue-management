from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist
import json
from datetime import time
from unittest.mock import patch, MagicMock
from manager.models import Queue
from participant.models import Participant, Notification
from manager.utils.category_handler import CategoryHandlerFactory


class ParticipantViewsTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        # Create test users
        cls.user = User.objects.create_user(
            username='testuser',
            password='testpass123'
        )
        cls.unauthorized_user = User.objects.create_user(
            username='unauthorized',
            password='testpass123'
        )

        # Create test queue
        cls.queue = Queue.objects.create(
            name='Test Queue',
            created_by=cls.user,
            open_time = time(8, 0),
            close_time = time(18, 0),
            estimated_wait_time_per_turn = 5,
            average_service_duration = 10,
            is_closed = False,
            status = "normal",
            category = "restaurant",
            latitude = 40.7128,
            longitude = -74.0060,
        )

    def setUp(self):
        # Create client and login
        self.client = Client()
        self.client.login(username='testuser', password='testpass123')

        # Create test participant
        self.participant = Participant.objects.create(
            name='Test Participant',
            queue=self.queue,
            state='waiting',
            position=1,
            phone='1234567890',
            email='test@example.com'
        )

        # Set up mock handler
        self.patcher = patch('manager.utils.category_handler.CategoryHandlerFactory.get_handler')
        self.mock_handler_factory = self.patcher.start()
        self.mock_handler = MagicMock()
        self.mock_handler.get_participant_set.return_value = Participant.objects.all()
        self.mock_handler.get_queue_object.return_value = self.queue
        self.mock_handler_factory.return_value = self.mock_handler

    def test_notify_participant(self):
        url = reverse('manager:notify_participant', args=[self.participant.id])
        data = {'message': 'Test notification'}

        # Test successful notification
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(json.loads(response.content)['status'], 'success')

        # Verify notification was created
        notification = Notification.objects.filter(participant=self.participant).first()
        self.assertIsNotNone(notification)
        self.assertEqual(notification.message, 'Test notification')

        # Test with non-existent participant
        response = self.client.post(reverse('manager:notify_participant', args=[99999]), data)
        self.assertEqual(response.status_code, 404)

        # Test GET method (should fail)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_delete_participant(self):
        url = reverse('manager:delete_participant', args=[self.participant.id])

        # Test successful deletion by queue owner
        response = self.client.delete(url)
        self.assertEqual(response.status_code, 200)

        # Create new participant for unauthorized test
        new_participant = Participant.objects.create(
            name='Test Participant 2',
            queue=self.queue,
            state='waiting',
            position=1
        )

        # Test unauthorized deletion
        self.client.logout()
        self.client.login(username='unauthorized', password='testpass123')
        response = self.client.delete(
            reverse('manager:delete_participant', args=[new_participant.id])
        )
        self.assertEqual(response.status_code, 403)

        # Test POST method (should fail)
        response = self.client.post(url)
        self.assertEqual(response.status_code, 405)

    def test_serve_participant(self):
        url = reverse('manager:serve_participant', args=[self.participant.id])
        data = {'resource_id': '1'}

        # Test successful serving
        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])

        # Test invalid state transition
        self.participant.state = 'completed'
        self.participant.save()

        response = self.client.post(
            url,
            data=json.dumps(data),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

        # Test invalid JSON
        response = self.client.post(
            url,
            data='invalid json',
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 400)

        # Test GET method (should fail)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_complete_participant(self):
        url = reverse('manager:complete_participant', args=[self.participant.id])

        # Set up participant in serving state
        self.participant.state = 'serving'
        self.participant.save()

        # Test successful completion by queue owner
        response = self.client.post(url)
        self.assertEqual(response.status_code, 200)
        response_data = json.loads(response.content)
        self.assertIn('serving_list', response_data)
        self.assertIn('completed_list', response_data)

        # Test unauthorized completion
        self.client.logout()
        self.client.login(username='unauthorized', password='testpass123')
        response = self.client.post(url)
        self.assertEqual(response.status_code, 403)

        # Test invalid state transition
        self.client.logout()
        self.client.login(username='testuser', password='testpass123')
        self.participant.state = 'waiting'
        self.participant.save()

        response = self.client.post(url)
        self.assertEqual(response.status_code, 400)

        # Test GET method (should fail)
        response = self.client.get(url)
        self.assertEqual(response.status_code, 405)

    def test_edit_participant(self):
        url = reverse('manager:edit_participant', args=[self.participant.id])
        data = {
            'name': 'Updated Name',
            'phone': '9876543210',
            'email': 'updated@example.com',
            'notes': 'Updated notes',
            'resource': 'Table 1',
            'special_1': 'Special note 1',
            'special_2': 'Special note 2',
            'party_size': '4',
            'state': 'waiting'
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)
        self.mock_handler.update_participant.assert_called_once()

    def test_add_participant(self):
        url = reverse('manager:add_participant', args=[self.queue.id])
        data = {
            'name': 'New Participant',
            'phone': '5555555555',
            'email': 'new@example.com',
            'notes': 'Test notes',
            'special_1': 'Special 1',
            'special_2': 'Special 2'
        }

        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 302)  # Redirect status
        self.mock_handler.create_participant.assert_called_once()

    def tearDown(self):
        # Stop the patcher
        self.patcher.stop()

        # Clean up all created objects
        Participant.objects.all().delete()
        Notification.objects.all().delete()

    @classmethod
    def tearDownClass(cls):
        # Clean up the test data
        Queue.objects.all().delete()
        User.objects.all().delete()
        super().tearDownClass()