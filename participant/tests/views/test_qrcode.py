from django.test import TestCase, Client
from django.urls import reverse
from manager.models import Queue
from participant.models import Participant
from django.contrib.auth.models import User
from datetime import time


class QRcodeViewTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='password123')
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

        self.qrcode_url = reverse('participant:qrcode', kwargs={'participant_code': self.participant.code})

    def test_qrcode_view_get(self):
        """Test GET request for QR code view."""
        response = self.client.get(self.qrcode_url)

        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'participant/qrcode.html')

        context = response.context
        self.assertEqual(context['participant'], self.participant)
        self.assertEqual(context['queue'], self.queue)

    def test_qrcode_view_invalid_participant_code(self):
        """Test behavior when participant code does not exist."""
        invalid_url = reverse('participant:qrcode', kwargs={'participant_code': 'invalidcode'})
        response = self.client.get(invalid_url)

        self.assertEqual(response.status_code, 404)

    def test_qrcode_generation(self):
        """Test QR code generation and context."""
        response = self.client.get(self.qrcode_url)

        context = response.context
        self.assertIn('qr_image', context)

        qr_image_data = context['qr_image']
        self.assertTrue(qr_image_data.startswith('iVBORw0KGgo'))

    def test_qrcode_url_included(self):
        """Test that the QR code contains the correct URL."""
        response = self.client.get(self.qrcode_url)
        context = response.context
        participant = context['participant']

        expected_relative_url = reverse('participant:queue_status', kwargs={'participant_code': participant.code})
        self.assertIn(expected_relative_url, response.content.decode())


