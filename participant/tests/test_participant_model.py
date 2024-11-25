from django.test import TestCase
from django.utils import timezone
from participant.models import Participant, RestaurantParticipant
from manager.models import Queue, RestaurantQueue, Table
from manager.models import Queue, RestaurantQueue, Table, Resource
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
        self.resource = Resource.objects.create(name="Test Resource", status="available")

    def test_generate_unique_queue_code(self):
        """Test that a unique queue code is generated for each participant."""
        code = self.participant.code
        self.assertEqual(len(code), 12)
        self.assertTrue(code.isalnum())
        self.assertEqual(Participant.objects.filter(code=code).count(), 1)

    def test_save_method(self):
        """Test save method for unique code and position generation."""
        self.assertIsNotNone(self.participant.code)
        self.assertEqual(self.participant.position, 1)

    def test_update_position(self):
        """Test updating the position of the participant."""
        self.participant.update_position(3)
        self.assertEqual(self.participant.position, 3)

        with self.assertRaises(ValueError) as context:
            self.participant.update_position(0)  # Attempt to set position to 0

        # Verify the exception message
        self.assertEqual(str(context.exception), "Position must be positive.")

        with self.assertRaises(ValueError) as context:
            self.participant.update_position(-5)  # Attempt to set position to a negative value

        # Verify the exception message
        self.assertEqual(str(context.exception), "Position must be positive.")

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
        self.assertEqual(self.participant.get_wait_time(), 0)
        self.participant.state = 'waiting'
        self.participant.joined_at = timezone.localtime() - timedelta(
            minutes=10)
        self.participant.save()
        self.assertEqual(self.participant.get_wait_time(), 10)

    def test_get_wait_time_with_service_started(self):
        """Test get_wait_time method when service_started_at is set."""
        # Set up a participant with joined_at and service_started_at
        self.participant.joined_at = timezone.now() - timedelta(minutes=20)
        self.participant.service_started_at = timezone.now() - timedelta(minutes=10)
        self.participant.state = 'serving'
        self.participant.save()

        # Call get_wait_time and verify the calculated wait time
        wait_time = self.participant.get_wait_time()
        self.assertEqual(wait_time, 10)

    def test_get_service_duration_serving(self):
        """Test get_service_duration when participant is serving."""
        # Set up a participant in 'serving' state
        self.participant.state = 'serving'
        self.participant.service_started_at = timezone.now() - timedelta(minutes=15)
        self.participant.save()

        # Call get_service_duration and verify the result
        service_duration = self.participant.get_service_duration()
        self.assertEqual(service_duration, 15)  # Service started 15 minutes ago

    def test_get_service_duration_completed(self):
        """Test get_service_duration when participant has completed service."""
        # Set up a participant in 'completed' state
        self.participant.state = 'completed'
        self.participant.service_started_at = timezone.now() - timedelta(minutes=30)
        self.participant.service_completed_at = timezone.now() - timedelta(minutes=10)
        self.participant.save()

        # Call get_service_duration and verify the result
        service_duration = self.participant.get_service_duration()
        self.assertEqual(service_duration, 20)  # 30 minutes started - 10 minutes completed

    def test_get_service_duration_default(self):
        """Test get_service_duration when no service has started."""
        # Set up a participant without service started or completed
        self.participant.state = 'waiting'  # Neither 'serving' nor 'completed'
        self.participant.service_started_at = None
        self.participant.service_completed_at = None
        self.participant.save()

        # Call get_service_duration and verify the result
        service_duration = self.participant.get_service_duration()
        self.assertEqual(service_duration, 0)

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

    def test_assign_to_resource(self):
        """Test assign_to_resource method."""
        # Ensure the resource is available and associated with the queue
        self.resource.status = 'available'
        self.resource.queue = self.queue  # Associate the resource with the queue
        self.resource.save()

        # Test resource assignment without required capacity
        self.participant.assign_to_resource()
        self.resource.refresh_from_db()  # Reload the resource from the database
        self.assertEqual(self.participant.resource, self.resource)
        self.assertEqual(self.resource.status, 'busy')  # Verify status update

        # Reset resource and test with required capacity
        self.resource.status = 'available'
        self.resource.capacity = 10
        self.resource.save()
        self.participant.assign_to_resource(required_capacity=5)
        self.resource.refresh_from_db()  # Reload the resource
        self.assertEqual(self.participant.resource, self.resource)
        self.assertEqual(self.resource.status, 'busy')

    def test_assign_to_resource_no_available_resources(self):
        """Test assign_to_resource raises ValueError when no resources are available."""
        # Ensure there are no available resources
        self.resource.status = 'busy'  # Set the resource to busy
        self.resource.save()

        # Attempt to assign a resource and expect a ValueError
        with self.assertRaises(ValueError) as context:
            self.participant.assign_to_resource()

        # Verify the exception message
        self.assertEqual(str(context.exception), "No available resources")


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
        self.table = Table.objects.create(name='A01', capacity=4)
        self.restaurant_queue.resources.add(self.table)

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
