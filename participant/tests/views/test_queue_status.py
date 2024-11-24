from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from manager.models import Queue
from participant.models import Participant
from datetime import time
import json
from unittest.mock import patch


class QueueStatusTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password123')
        self.client = Client()
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
            latitude=55.7128,
            longitude=-77.0060,
        )
        self.participant = Participant.objects.create(
            queue=self.queue,
            name='John Doe',
            position=1,
            code='12345',
        )

        # URLs
        self.status_url = reverse('participant:queue_status', kwargs={'participant_code': self.participant.code})
        self.sse_url = reverse('participant:sse_queue_status', kwargs={'participant_code': self.participant.code})
        self.leave_url = reverse('participant:participant_leave', kwargs={'participant_code': self.participant.code})

    def test_queue_status_view_context(self):
        """Test the context data in QueueStatusView."""
        response = self.client.get(self.status_url)

        # Assert response status and template
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'participant/status.html')

        # Assert context data
        context = response.context
        self.assertEqual(context['queue'], self.queue)
        self.assertEqual(context['participant'], self.participant)
        self.assertIn('participants_in_queue', context)
        self.assertQuerySetEqual(
            context['participants_in_queue'],
            list(Participant.objects.filter(queue=self.queue).order_by('joined_at')),
        )

    @patch('manager.utils.category_handler.CategoryHandlerFactory.get_handler')
    def test_sse_queue_status(self, mock_handler_factory):
        """Test server-sent events for queue status."""
        # Mock handler behavior
        mock_handler = mock_handler_factory.return_value
        mock_handler.get_participant_set.return_value.get.return_value = self.participant
        mock_handler.get_participant_data.return_value = {'position': 1, 'name': 'John Doe'}

        response = self.client.get(self.sse_url)

        # Assert streaming response type
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/event-stream')

        # Simulate the generator's behavior
        event_generator = response.streaming_content
        event_data = next(event_generator).decode('utf-8')
        self.assertIn('data: {"position": 1, "name": "John Doe"}', event_data)


    def test_participant_leave_success(self):
        """Test successful removal of a participant from the queue."""
        response = self.client.get(self.leave_url)

        # Assert the participant is removed and redirected to the welcome page
        self.assertRedirects(response, reverse('participant:welcome', kwargs={'queue_code': self.queue.code}))
        self.assertFalse(Participant.objects.filter(code=self.participant.code).exists())

    @patch('participant.models.Participant.delete', side_effect=Exception('Database error'))
    def test_participant_leave_exception(self, mock_delete):
        """Test participant leave when an exception occurs."""
        response = self.client.get(self.leave_url)

        # Assert redirection to the welcome page
        self.assertRedirects(response, reverse('participant:welcome', kwargs={'queue_code': self.queue.code}))

        # Verify the error message
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertIn('Error removing participant: Database error', str(messages[0]))

        # Verify the participant still exists
        self.assertTrue(Participant.objects.filter(code=self.participant.code).exists())

    def test_participant_leave_not_found(self):
        """Test leaving the queue with an invalid participant code."""
        invalid_leave_url = reverse('participant:participant_leave', kwargs={'participant_code': 'invalidcode'})
        response = self.client.get(invalid_leave_url)

        # Assert redirection to the home page with an error message
        self.assertRedirects(response, reverse('participant:home'))
        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Couldn't find the participant in the queue.")

    def test_set_location_success(self):
        """Test successful setting of user location."""
        data = {'lat': 40.7128, 'lon': -74.0060}
        response = self.client.post(reverse('participant:set_location'), data=json.dumps(data),
                                    content_type='application/json')

        # Assert response status and content
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'status': 'success'})

        # Verify session data
        session = self.client.session
        self.assertEqual(session['user_lat'], 40.7128)
        self.assertEqual(session['user_lon'], -74.0060)

    def test_set_location_failure(self):
        """Test failure to set location due to missing data."""
        data = {'lat': None, 'lon': None}
        response = self.client.post(reverse('participant:set_location'), data=json.dumps(data),
                                    content_type='application/json')

        # Assert response status and content
        self.assertEqual(response.status_code, 400)
        self.assertJSONEqual(response.content, {'status': 'failed'})
