from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from manager.models import Queue
from unittest.mock import patch
from datetime import time


class DeleteQueueTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create test users
        self.creator = User.objects.create_user(
            username='creator', password='password123'
        )
        self.other_user = User.objects.create_user(
            username='otheruser', password='password123'
        )

        # Create a test queue
        self.queue = Queue.objects.create(
            name='Test Queue',
            created_by=self.creator,
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

        # Endpoint for deleting queues
        self.delete_queue_url = reverse('manager:delete_queue', kwargs={'queue_id': self.queue.id})

    def test_delete_queue_success(self):
        # Log in as the queue creator
        self.client.login(username='creator', password='password123')

        # Send DELETE request
        response = self.client.delete(self.delete_queue_url)

        # Assertions
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(
            response.content,
            {'success': 'Queue deleted successfully.'}
        )
        self.assertFalse(Queue.objects.filter(pk=self.queue.id).exists())

    def test_delete_queue_not_found(self):
        # Log in as the queue creator
        self.client.login(username='creator', password='password123')

        # Send DELETE request to a non-existent queue
        non_existent_url = reverse('manager:delete_queue', kwargs={'queue_id': 9999})
        response = self.client.delete(non_existent_url)

        # Assertions
        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(
            response.content,
            {'error': 'Queue not found.'}
        )

    def test_delete_queue_unauthorized(self):
        # Log in as a different user
        self.client.login(username='otheruser', password='password123')

        # Send DELETE request
        response = self.client.delete(self.delete_queue_url)

        # Assertions
        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(
            response.content,
            {'error': 'Unauthorized.'}
        )

    @patch('manager.views.Queue.delete')  # Mock delete method to raise an exception
    def test_delete_queue_unexpected_error(self, mock_delete):
        # Simulate an unexpected exception
        mock_delete.side_effect = Exception('Unexpected error occurred')

        # Log in as the queue creator
        self.client.login(username='creator', password='password123')

        # Send DELETE request
        response = self.client.delete(self.delete_queue_url)

        # Assertions
        self.assertEqual(response.status_code, 500)
        self.assertJSONEqual(
            response.content,
            {'error': 'Unexpected error occurred'}
        )
