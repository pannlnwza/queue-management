from django.test import TestCase
from django.utils import timezone
from participant.models import Participant, RestaurantParticipant
from manager.models import Queue, RestaurantQueue, Resource
from django.contrib.auth.models import User
from datetime import timedelta


class ParticipantModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser',
                                             password='testpass')
        self.queue = Queue.objects.create(
            name='General Queue',
            description='A general test queue.',
            created_by=self.user,
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            longitude=100.5163,
            latitude=13.7285
        )
        self.participant = Participant.objects.create(
            name='John Doe',
            email='john@example.com',
            phone='1234567890',
            queue=self.queue,
            position=1,
            note='Test note'
        )

    def test_generate_unique_queue_code(self):
        """Test that a unique queue code is generated for each participant."""
        code = self.participant.code
        self.assertEqual(len(code), 6)
        self.assertTrue(code.isalnum())
        self.assertEqual(Participant.objects.filter(code=code).count(), 1)

    def test_update_position(self):
        """Test updating the position of the participant."""
        self.participant.update_position(3)
        self.assertEqual(self.participant.position, 3)

    def test_calculate_estimated_wait_time(self):
        """Test that estimated wait time is calculated correctly."""
        self.assertEqual(self.participant.calculate_estimated_wait_time(), 0)

    def test_start_service(self):
        """Test that starting service changes the participant's state."""
        self.participant.start_service()
        self.assertEqual(self.participant.state, 'serving')
        self.assertIsNotNone(self.participant.service_started_at)

    def test_get_wait_time(self):
        """Test the wait time calculation."""
        self.assertEqual(self.participant.get_wait_time(), 0)  #
        self.participant.state = 'waiting'
        self.participant.joined_at = timezone.localtime() - timedelta(
            minutes=10)
        self.participant.save()
        self.assertEqual(self.participant.get_wait_time(), 10)

    def test_get_service_duration(self):
        """Test the service duration calculation."""
        self.participant.start_service()
        service_duration_minutes = 5
        self.participant.service_started_at = timezone.localtime()
        self.participant.save()
        self.participant.service_completed_at = self.participant.service_started_at + timedelta(
            minutes=service_duration_minutes)
        self.participant.state = 'completed'
        self.participant.save()

        # Refresh participant instance
        self.participant.refresh_from_db()

        # Now we should get the duration equal to service_duration_minutes
        self.assertEqual(self.participant.get_service_duration(),
                         service_duration_minutes)

    def test_remove_old_completed_participants(self):
        """Test that old completed participants are removed."""
        old_participant = Participant.objects.create(
            name='Old Participant',
            queue=self.queue,
            state='completed',
            service_completed_at=timezone.now() - timedelta(days=31)
        )
        Participant.remove_old_completed_participants()
        self.assertFalse(
            Participant.objects.filter(id=old_participant.id).exists())


class RestaurantParticipantModelTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser',
                                             password='testpass')
        self.restaurant_queue = RestaurantQueue.objects.create(
            name='Test Restaurant Queue',
            description='A test restaurant queue.',
            created_by=self.user,
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            longitude=100.5163,
            latitude=13.7285
        )
        self.table = Resource.objects.create(name='A01', capacity=4)
        self.restaurant_queue.tables.add(self.table)

        self.restaurant_participant = RestaurantParticipant.objects.create(
            name='Alice Doe',
            queue=self.restaurant_queue,
            position=1,
            party_size=2
        )



    def test_participant_str(self):
        """Test the string representation of the participant."""
        self.assertEqual(str(self.restaurant_participant),
                         'Alice Doe - waiting')
