from django.test import TestCase
from django.contrib.auth.models import User
from queue_manager.models import Queue, Participant


class QueueModelTest(TestCase):
    """
    Tests for the Queue model.
    """

    def setUp(self):
        """
        Set up the test case by creating a test user and a test queue.
        """
        self.user = User.objects.create(username='creator')
        self.queue = Queue.objects.create(name='Test Queue', created_by=self.user)

    def test_queue_creation(self):
        """
        Test that a queue is created correctly.
        """
        self.assertEqual(self.queue.name, 'Test Queue')

    def test_generate_unique_code(self):
        """
        Test that a unique queue code is generated.
        """
        code = Queue.generate_unique_code()
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isalnum())

    def test_update_estimated_wait_time(self):
        """
        Test the estimated wait time update method.
        """
        participant = Participant.objects.create(user=self.user, queue=self.queue, position=1)
        self.queue.update_estimated_wait_time(average_time_per_participant=10)
        self.assertEqual(self.queue.estimated_wait_time, 10)


class ParticipantModelTest(TestCase):
    """
    Tests for the Participant model.
    """

    def setUp(self):
        """
        Set up the test case by creating a test user, a test queue, and a participant.
        """
        self.user = User.objects.create(username='participant')
        self.queue = Queue.objects.create(name='Test Queue')
        self.participant = Participant.objects.create(user=self.user, queue=self.queue, position=1)

    def test_participant_creation(self):
        """
        Test that a participant is created correctly.
        """
        self.assertEqual(self.participant.user.username, 'participant')
        self.assertEqual(self.participant.position, 1)
