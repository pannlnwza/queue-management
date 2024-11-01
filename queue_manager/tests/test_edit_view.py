from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib import messages
from queue_manager.models import Queue


class EditQueueViewTests(TestCase):
    def setUp(self):
        """Set up the test case by creating a user and a queue."""
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.other_user = User.objects.create_user(username='otheruser', password='otherpassword')
        self.queue = Queue.objects.create(name='Test Queue', created_by=self.user, capacity=10)

    def test_edit_queue_success(self):
        """Test that a user can successfully edit their own queue."""
        self.client.login(username='testuser', password='testpassword')
        response = self.client.post(reverse('queue:edit_queue', kwargs={'pk': self.queue.pk}), {
            'name': 'Updated Queue',
            'description': 'Updated description',
            'is_closed': 'false',
            'action': 'edit_queue'
        })

        self.queue.refresh_from_db()
        self.assertEqual(self.queue.name, 'Updated Queue')
        self.assertEqual(self.queue.description, 'Updated description')
        self.assertFalse(self.queue.is_closed)
        self.assertEqual(response.status_code, 200)
        self.assertIn("Queue updated successfully.", [str(m) for m in messages.get_messages(response.wsgi_request)])

    def test_edit_queue_unauthorized_access(self):
        """Test that a user who is not the creator cannot edit the queue."""
        self.client.login(username='otheruser', password='otherpassword')
        response = self.client.get(reverse('queue:edit_queue', kwargs={'pk': self.queue.pk}))

        self.assertEqual(response.status_code, 302)  # Should redirect
        self.assertRedirects(response, reverse('queue:manage_queues'))
        self.assertIn("You do not have permission to edit this queue.", [str(m) for m in messages.get_messages(response.wsgi_request)])

    def test_queue_status_update(self):
        """Test that the queue status can be toggled."""
        self.client.login(username='testuser', password='testpassword')
        initial_status = self.queue.is_closed

        response = self.client.post(reverse('queue:edit_queue', kwargs={'pk': self.queue.pk}), {
            'action': 'queue_status'
        })

        self.queue.refresh_from_db()
        self.assertNotEqual(self.queue.is_closed, initial_status)  # Status should be toggled
        self.assertEqual(response.status_code, 302)  # Redirects to manage queues
        self.assertIn("Queue status updated successfully.", [str(m) for m in messages.get_messages(response.wsgi_request)])
