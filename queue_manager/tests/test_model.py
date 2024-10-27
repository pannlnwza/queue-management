from django.test import TestCase
from django.contrib.auth.models import User
from queue_manager.models import Queue, Participant, Notification
from django.utils import timezone


class QueueModelTest(TestCase):
    """
    Tests for the Queue model.
    """

    def setUp(self):
        """
        Set up the test case by creating a test user and a test queue.
        """
        self.user = User.objects.create(username='user1')
        self.user2 = User.objects.create(username='user2')
        self.queue = Queue.objects.create(name='Test Queue', created_by=self.user, capacity=10)

    def test_queue_creation(self):
        """
        Test that a queue is created correctly.
        """
        self.assertEqual(self.queue.name, 'Test Queue')

    def test_update_estimated_wait_time_per_turn(self):
        self.queue.update_estimated_wait_time_per_turn(10)
        self.assertEqual(self.queue.estimated_wait_time_per_turn, 10)

        self.queue.update_estimated_wait_time_per_turn(20)
        self.assertEqual(self.queue.estimated_wait_time_per_turn, 15)

    def test_get_number_of_participants(self):
        self.assertEqual(self.queue.get_number_of_participants(), 0)
        Participant.objects.create(queue=self.queue, user=self.user, position=1)
        self.assertEqual(self.queue.get_number_of_participants(), 1)

    def test_is_full(self):
        self.queue.capacity = 2
        Participant.objects.create(queue=self.queue, user=self.user, position=1)
        Participant.objects.create(queue=self.queue, user=self.user2, position=2)
        self.assertTrue(self.queue.is_full())


class ParticipantModelTest(TestCase):
    """
    Tests for the Participant model.
    """

    def setUp(self):
        """
        Set up the test case by creating a test user, a test queue, and a participant.
        """
        self.user = User.objects.create(username='participant')
        self.queue = Queue.objects.create(name='Test Queue', capacity=10)
        self.participant = Participant.objects.create(user=self.user, queue=self.queue, position=1)

    def test_participant_creation(self):
        """
        Test that a participant is created correctly.
        """
        self.assertEqual(self.participant.user.username, 'participant')
        self.assertEqual(self.participant.position, 1)

class NotificationModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.queue = Queue.objects.create(
            name="Test Queue",
            description="A test queue.",
            created_by=self.user,
            capacity=5,
            category='restaurant'
        )
        self.participant = Participant.objects.create(user=self.user, queue=self.queue, position=1,
                                                      joined_at=timezone.localtime(timezone.now()))

    def test_notification_creation(self):
        notification = Notification.objects.create(
            queue=self.queue,
            participant=self.participant,
            message="Your turn is near!"
        )
        self.assertEqual(notification.message, "Your turn is near!")
        self.assertEqual(notification.participant, self.participant)
