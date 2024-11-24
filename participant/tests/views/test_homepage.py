from django.test import TestCase, RequestFactory, Client
from django.urls import reverse
from unittest.mock import patch, MagicMock
from participant.views import HomePageView
from manager.models import Queue
from django.contrib.auth.models import User
from participant.models import Notification, Participant


class TestHomePageView(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.view = HomePageView.as_view()

    @patch('manager.models.Queue.get_nearby_queues')
    @patch('manager.models.Queue.get_top_featured_queues')
    def test_get_context_data_with_location(self, mock_get_top_featured_queues, mock_get_nearby_queues):
        # Mock methods
        mock_get_nearby_queues.return_value = ['Queue1', 'Queue2']
        mock_get_top_featured_queues.side_effect = lambda category: [f'{category}_Queue1', f'{category}_Queue2']

        # Create a request with session data
        request = self.factory.get(reverse('participant:home'))
        request.session = {'user_lat': '12.34', 'user_lon': '56.78'}

        # Execute the view
        response = self.view(request)

        # Check the response
        self.assertEqual(response.status_code, 200)

        # Verify context
        self.assertIn('nearby_queues', response.context_data)
        self.assertIn('num_nearby_queues', response.context_data)
        self.assertEqual(response.context_data['num_nearby_queues'], 2)
        self.assertEqual(response.context_data['nearby_queues'], ['Queue1', 'Queue2'])

        for category in ['restaurant', 'general', 'hospital', 'bank']:
            self.assertIn(f'{category}_featured_queues', response.context_data)
            self.assertEqual(response.context_data[f'{category}_featured_queues'], [f'{category}_Queue1', f'{category}_Queue2'])

    def test_get_context_data_without_location(self):
        # Create a request without session data
        request = self.factory.get(reverse('participant:home'))
        request.session = {}

        # Execute the view
        response = self.view(request)

        # Check the response
        self.assertEqual(response.status_code, 200)

        # Verify context
        self.assertIn('error', response.context_data)
        self.assertEqual(response.context_data['error'], "Location not provided. Please enable location services.")

    def test_get_context_data_invalid_location(self):
        # Create a request with invalid latitude/longitude
        request = self.factory.get(reverse('participant:home'))
        request.session = {'user_lat': 'invalid_lat', 'user_lon': 'invalid_lon'}

        # Execute the view
        response = self.view(request)

        # Check the response
        self.assertEqual(response.status_code, 200)

        # Verify context
        self.assertIn('error', response.context_data)
        self.assertEqual(response.context_data['error'], "Invalid latitude or longitude provided.")




class MarkNotificationAsReadTests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create test user and login
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client.login(username='testuser', password='password123')

        # Create test queue and participant
        self.queue = Queue.objects.create(
            name="Test general Queue",
            category="general",
            created_by=self.user,
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=55.7128,
            longitude=-77.0060,
        )
        self.participant = Participant.objects.create(
            queue=self.queue,
            name="John Doe",
            position=1,
            code="12345"
        )

        # Create a notification for the participant
        self.notification = Notification.objects.create(
            queue=self.queue,
            participant=self.participant,
            message="Test notification",
            is_read=False
        )

        # URL for marking notification as read
        self.mark_notification_url = reverse('participant:mark_notification_as_read', kwargs={'notification_id': self.notification.id})

    def test_mark_notification_as_read_success(self):
        """Test marking a notification as read successfully."""
        response = self.client.post(self.mark_notification_url)

        # Assert response status and content
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {"status": "success"})

        # Verify the notification is marked as read
        self.notification.refresh_from_db()
        self.assertTrue(self.notification.is_read)

    def test_mark_notification_as_read_not_found(self):
        """Test marking a non-existent notification as read."""
        invalid_url = reverse('participant:mark_notification_as_read', kwargs={'notification_id': 9999})
        response = self.client.post(invalid_url)

        # Assert response status and content
        self.assertEqual(response.status_code, 404)
        self.assertJSONEqual(response.content, {"status": "error", "message": "Notification not found"})

    def test_mark_notification_as_read_invalid_method(self):
        """Test accessing the endpoint with an invalid method."""
        response = self.client.get(self.mark_notification_url)

        # Assert response status and content
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {"status": "error", "message": "Invalid request"})