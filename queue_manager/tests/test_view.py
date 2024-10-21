from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from queue_manager.models import Queue, Participant
from django.contrib.messages import get_messages


class QueueViewsTestCase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client.login(username='testuser', password='password')
        self.user2 = User.objects.create_user(username='user2', password='password')
        self.queue = Queue.objects.create(name='Test Queue', code='TEST123', created_by=self.user)

    def test_index_view_authenticated(self):
        """Test accessing the index view as an authenticated user"""
        response = self.client.get(reverse('queue:index'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'queue_manager/index.html')
        self.assertIn('queue_list', response.context)

    def test_create_queue_view(self):
        """Test creating a queue as an authenticated user"""
        response = self.client.post(reverse('queue:create_q'), {
            'name': 'New Test Queue',
            'description': 'A new test queue.'
        })
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('queue:index'))
        self.assertTrue(Queue.objects.filter(name='New Test Queue').exists())

    def test_join_queue_valid_code(self):
        """Test joining a queue with a valid code"""
        response = self.client.post(reverse('queue:join'), {'queue_code': self.queue.code})
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('queue:index'))
        self.assertTrue(Participant.objects.filter(user=self.user, queue=self.queue).exists())

    def test_join_queue_invalid_code(self):
        """Test joining a queue with an invalid code"""
        response = self.client.post(reverse('queue:join'), {'queue_code': 'INVALIDCODE'})
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('queue:index'))
        self.assertIn('Invalid queue code.', [message.message for message in messages])

    def test_queue_dashboard_view_owner(self):
        """Test accessing the dashboard view as the owner of the queue"""
        response = self.client.get(reverse('queue:dashboard', args=[self.queue.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'queue_manager/general_dashboard.html')
        self.assertEqual(response.context['queue'], self.queue)

    def test_queue_dashboard_view_non_owner(self):
        """Test accessing the dashboard view as the owner of the queue"""
        self.client.login(username='user2', password='password')

        # Test accessing the dashboard view as a non-owner
        response = self.client.get(reverse('queue:dashboard', args=[self.queue.pk]))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('queue:index'))
        self.assertIn('You are not the owner of this queue.', [message.message for message in messages])

    def test_queue_dashboard_view_non_existent(self):
        """Test accessing a non-existent queue's dashboard"""
        response = self.client.get(reverse('queue:dashboard', args=[999]))
        messages = list(get_messages(response.wsgi_request))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, reverse('queue:index'))
        self.assertIn('Queue does not exist.', [message.message for message in messages])
