from django.test import TestCase
from manager.models import Resource, Queue
from participant.models import Participant
from django.utils.timezone import now
from datetime import timedelta

class ResourceModelTests(TestCase):

    def setUp(self):
        self.queue = Queue.objects.create(
            name="Test Queue",
            category="general",
            latitude=0.0,
            longitude=0.0,
        )
        self.resource = Resource.objects.create(
            name="Resource 1",
            capacity=2,
            status="available",
            queue=self.queue,
        )
        self.participant = Participant.objects.create(
            queue=self.queue,
            state="waiting",
            joined_at=now(),
        )

    def test_assign_to_participant(self):
        """Test assigning a resource to a participant."""
        self.resource.assign_to_participant(self.participant, capacity=1)
        self.assertEqual(self.resource.status, "busy")
        self.assertEqual(self.resource.assigned_to, self.participant)
        self.assertEqual(self.participant.resource, self.resource)

    def test_assign_to_participant_invalid_status(self):
        """Test assigning a resource that is not available."""
        self.resource.status = "busy"
        self.resource.save()
        with self.assertRaises(ValueError) as context:
            self.resource.assign_to_participant(self.participant)
        self.assertEqual(str(context.exception), "This resource is not available.")

    def test_assign_to_participant_insufficient_capacity(self):
        """Test assigning a resource with insufficient capacity."""
        with self.assertRaises(ValueError) as context:
            self.resource.assign_to_participant(self.participant, capacity=3)
        self.assertEqual(str(context.exception), "This resource cannot accommodate the party size.")

    def test_free(self):
        """Test freeing a resource."""
        self.resource.assign_to_participant(self.participant)
        self.resource.free()
        self.assertEqual(self.resource.status, "available")
        self.assertIsNone(self.resource.assigned_to)
        self.assertIsNone(self.participant.resource)

    def test_is_assigned(self):
        """Test checking if a resource is assigned."""
        self.assertFalse(self.resource.is_assigned())
        self.resource.assign_to_participant(self.participant)
        self.assertTrue(self.resource.is_assigned())

    def test_total(self):
        """Test getting the total participants assigned to a resource."""
        self.resource.assign_to_participant(self.participant)
        self.assertEqual(self.resource.total, 1)

    def test_served(self):
        """Test getting the number of served participants."""
        self.participant.state = "serving"
        self.participant.resource = self.resource
        self.participant.save()
        self.assertEqual(self.resource.served, 1)

    def test_dropoff(self):
        """Test getting the number of dropoff participants."""
        self.participant.state = "cancelled"
        self.participant.resource = self.resource
        self.participant.save()
        self.assertEqual(self.resource.dropoff, 1)

    def test_completed(self):
        """Test getting the number of completed participants."""
        self.participant.state = "completed"
        self.participant.resource = self.resource
        self.participant.save()
        self.assertEqual(self.resource.completed, 1)

    # def test_avg_wait_time(self):
    #     """Test calculating the average wait time."""
    #     participant1 = Participant.objects.create(
    #         queue=self.queue,
    #         state="completed",
    #         joined_at=now() - timedelta(minutes=30),
    #         service_started_at=now() - timedelta(minutes=20),
    #     )
    #     participant2 = Participant.objects.create(
    #         queue=self.queue,
    #         state="completed",
    #         joined_at=now() - timedelta(minutes=60),
    #         service_started_at=now() - timedelta(minutes=50),
    #     )
    #     participant1.resource = self.resource
    #     participant2.resource = self.resource
    #     participant1.save()
    #     participant2.save()
    #     self.assertEqual(self.resource.avg_wait_time, "20 mins")

    def test_avg_serve_time(self):
        """Test calculating the average service duration."""
        participant1 = Participant.objects.create(
            queue=self.queue,
            state="completed",
            service_started_at=now() - timedelta(minutes=30),
            service_completed_at=now() - timedelta(minutes=20),
        )
        participant2 = Participant.objects.create(
            queue=self.queue,
            state="completed",
            service_started_at=now() - timedelta(minutes=50),
            service_completed_at=now() - timedelta(minutes=30),
        )
        participant1.resource = self.resource
        participant2.resource = self.resource
        participant1.save()
        participant2.save()
        self.assertEqual(self.resource.avg_serve_time, "15 mins")
