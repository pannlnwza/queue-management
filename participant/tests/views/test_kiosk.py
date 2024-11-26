from django.test import TestCase, Client
from django.urls import reverse
from manager.models import Queue
from participant.models import Participant
from unittest.mock import patch
from datetime import time
from django.contrib.auth.models import User


class KioskViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.queue = Queue.objects.create(
            name="Test Queue",
            category="restaurant",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=47.7128,
            longitude=-54.0060,
        )

        self.kiosk_url = reverse('participant:kiosk', kwargs={'queue_code': self.queue.code})

    def test_kiosk_view_get(self):
        """Test the kiosk view GET request."""
        response = self.client.get(self.kiosk_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'participant/kiosk.html')
        self.assertIn('queue', response.context)
        self.assertEqual(response.context['queue'], self.queue)

    @patch('manager.utils.category_handler.CategoryHandlerFactory.get_handler')
    def test_kiosk_view_form_valid(self, mock_handler_factory):
        """Test successful form submission."""
        mock_handler = mock_handler_factory.return_value
        mock_participant = Participant(queue=self.queue, name="John Doe", position=1, code="12345")
        mock_handler.create_participant.return_value = mock_participant

        self.queue.category = "restaurant"
        self.queue.save()

        form_data = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '1234567890',
            'special_1': 4,
            'special_2': 'dine_in',
            'note': 'Near the window',
        }

        response = self.client.post(self.kiosk_url, data=form_data)

        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response,
                             reverse('participant:qrcode', kwargs={'participant_code': mock_participant.code}))

        mock_handler.create_participant.assert_called_once_with({
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '1234567890',
            'special_1': 4,
            'special_2': 'dine_in',
            'note': 'Near the window',
            'queue': self.queue,
        })

    def test_kiosk_view_form_invalid(self):
        """Test invalid form submission."""
        form_data = {
            'name': '',
            'phone': '1234567890',
            'email': 'invalid-email',
        }
        response = self.client.post(self.kiosk_url, data=form_data)

        # Verify the form is invalid and the template is re-rendered
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'participant/kiosk.html')
        self.assertTrue(response.context['form'].errors)

    def test_kiosk_view_queue_not_found(self):
        """Test behavior when queue is not found."""
        invalid_url = reverse('participant:kiosk', kwargs={'queue_code': 'invalidcode555'})
        response = self.client.get(invalid_url)

        self.assertEqual(response.status_code, 404)
