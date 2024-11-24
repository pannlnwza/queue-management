from django.test import TestCase, RequestFactory
from django.urls import reverse
from unittest.mock import patch, MagicMock
from participant.views import HomePageView
from manager.models import Queue


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
