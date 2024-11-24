from django.test import TestCase, Client
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth.models import User
from django.urls import reverse
from manager.models import Queue
from unittest.mock import patch
from datetime import time


class QueueViewTests(TestCase):
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

        self.delete_queue_url = reverse('manager:delete_queue', kwargs={'queue_id': self.queue.id})
        self.edit_queue_url = reverse('manager:edit_queue', kwargs={'queue_id': self.queue.id})

        self.patcher = patch('manager.utils.category_handler.CategoryHandlerFactory.get_handler')
        self.mock_get_handler = self.patcher.start()
        self.mock_get_handler.return_value.get_queue_object.return_value = self.queue

    def tearDown(self):
        # Stop the patcher
        self.patcher.stop()

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

    # ** function edit_queue not finish test yet**


    # def test_edit_queue_success(self):
    #     """Test successful update of queue settings."""
    #     self.client.login(username='creator', password='password123')
    #
    #     form_data = {
    #         'name': 'Updated Queue',
    #         'description': 'Updated description',
    #         'is_closed': 'off',
    #         'latitude': 41.0000,
    #         'longitude': -75.0000,
    #         'open_time': '09:00',
    #         'close_time': '17:00',
    #     }
    #     logo = SimpleUploadedFile("logo.jpg", b"fakeimagecontent", content_type="image/jpeg")
    #     response = self.client.post(self.edit_queue_url, form_data, FILES={'logo': logo})
    #
    #     # Refresh queue data from the database
    #     self.queue.refresh_from_db()
    #
    #     self.assertEqual(response.status_code, 302)
    #     self.assertEqual(self.queue.name, 'Updated Queue')
    #     self.assertEqual(self.queue.description, 'Updated description')
    #     self.assertEqual(self.queue.latitude, 41.0)
    #     self.assertEqual(self.queue.longitude, -75.0)
    #     self.assertEqual(self.queue.open_time, time(9, 0))
    #     self.assertEqual(self.queue.close_time, time(17, 0))
    #     self.assertFalse(self.queue.is_closed)
    #     self.assertEqual(self.queue.logo.name, 'logo.jpg')

    def test_edit_queue_invalid_time_format(self):
        """Test update with invalid time format."""
        self.client.login(username='creator', password='password123')

        form_data = {
            'name': 'Invalid Time Queue',
            'description': 'Testing invalid time format',
            'open_time': '25:00',
            'close_time': '17:00',
        }
        response = self.client.post(self.edit_queue_url, form_data)

        self.assertEqual(response.status_code, 302)
        messages = list(response.wsgi_request._messages)
        self.assertTrue(any("Invalid time format" in str(message) for message in messages))

    # def test_edit_queue_unauthorized(self):
    #     """Test unauthorized user cannot edit queue."""
    #     self.client.login(username='otheruser', password='password123')
    #
    #     form_data = {
    #         'name': 'Unauthorized Update',
    #         'description': 'Should not work',
    #         'latitude': 41.0000,
    #         'longitude': -75.0000,
    #     }
    #     response = self.client.post(self.edit_queue_url, form_data)
    #
    #
    #     self.assertEqual(response.status_code, 403)
    #     self.queue.refresh_from_db()
    #     self.assertNotEqual(self.queue.name, 'Unauthorized Update')
