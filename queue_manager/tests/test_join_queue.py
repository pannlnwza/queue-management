from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from queue_manager.models import Queue, Participant


class JoinQueueViewTests(TestCase):
    """
    Tests for the JoinQueue view functionality.
    """

    def setUp(self):
        """
        Set up the test case by creating a test user and a test queue.
        """
        self.user = User.objects.create_user(username='testuser', password='testpassword')
        self.queue = Queue.objects.create(name='Test Queue', description='A test queue')

    def test_join_queue_success(self):
        """
        Test that a user can successfully join a queue.
        """
        self.client.login(username='testuser', password='testpassword')
        response = self.client.post(reverse('queue:join'), {'queue_code': self.queue.code})

        participant_exists = Participant.objects.filter(user=self.user, queue=self.queue).exists()
        self.assertTrue(participant_exists)

        messages_list = list(response.wsgi_request._messages)
        self.assertEqual(str(messages_list[0]), "You have successfully joined the queue.")
        self.assertRedirects(response, reverse('queue:index'))

    def test_join_queue_already_in_queue(self):
        """
        Test that a user who is already in a queue receives the correct message.
        """
        self.client.login(username='testuser', password='testpassword')
        self.client.post(reverse('queue:join'), {'queue_code': self.queue.code})

        response = self.client.post(reverse('queue:join'), {'queue_code': self.queue.code})
        participant_count = Participant.objects.filter(user=self.user, queue=self.queue).count()
        self.assertEqual(participant_count, 1)

        self.assertRedirects(response, reverse('queue:index'))

    def test_join_queue_invalid_code(self):
        """
        Test that a user receives an error message when trying to join a queue with an invalid code.
        """
        self.client.login(username='testuser', password='testpassword')
        response = self.client.post(reverse('queue:join'), {'queue_code': 'INVALIDCODE'})

        participant_exists = Participant.objects.filter(user=self.user, queue=self.queue).exists()
        self.assertFalse(participant_exists)

        messages_list = list(response.wsgi_request._messages)
        self.assertEqual(str(messages_list[0]), "Invalid queue code.")
        self.assertRedirects(response, reverse('queue:index'))
