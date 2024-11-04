from django.test import TestCase
from django.contrib.auth.models import User
from manager.models import Queue, Table, RestaurantQueue
from participant.models import RestaurantParticipant, Participant
from django.utils import timezone

class QueueModelTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testtest', password='hackme11')
        self.queue = Queue.objects.create(
            name='Test Queue',
            description='This is a test queue',
            created_by=self.user,
            open_time=timezone.localtime(),
            close_time=timezone.localtime() + timezone.timedelta(hours=2),
            estimated_wait_time_per_turn=0,
            average_service_duration=0,
            status='normal',
            category='general'
        )

    def test_initial_estimated_wait_time(self):
        """Test the initial estimated wait time per turn."""
        self.assertEqual(self.queue.estimated_wait_time_per_turn, 0)

    def test_update_estimated_wait_time_per_turn(self):
        """Test updating the estimated wait time per turn after serving a participant."""
        # Simulate serving a participant with a specific time taken
        initial_time_taken = 5
        self.queue.update_estimated_wait_time_per_turn(initial_time_taken)
        self.assertEqual(self.queue.estimated_wait_time_per_turn, 5)
        additional_time_taken = 15
        self.queue.update_estimated_wait_time_per_turn(additional_time_taken)
        expected_wait_time = (5 + 15) / 2
        self.assertEqual(self.queue.estimated_wait_time_per_turn, expected_wait_time)

    def test_calculate_average_service_duration_multiple_serves(self):
        """Test updating the average service duration after multiple serves."""
        serve_times = [10, 20, 30]
        for time in serve_times:
            self.queue.calculate_average_service_duration(time)

        expected_average = (10 + 20 + 30) / 3
        self.assertEqual(self.queue.average_service_duration, expected_average)
        self.assertEqual(self.queue.completed_participants_count, 3)

    def test_get_number_of_participants(self):
        """Test getting the number of participants in the queue."""
        participant1 = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)
        participant2 = RestaurantParticipant.objects.create(queue=self.queue, party_size=4)

        self.assertEqual(self.queue.get_number_of_participants(), 2)

    def test_get_participants(self):
        """Test retrieving participants related to the queue."""
        participant = Participant.objects.create(
            name='Participant 1',
            queue=self.queue,
        )
        self.assertIn(participant, self.queue.get_participants())

    def test_edit_queue(self):
        """Test editing queue attributes."""
        self.queue.edit(name='Updated Queue', description='Updated description', is_closed=True, status='busy')
        self.queue.refresh_from_db()
        self.assertEqual(self.queue.name, 'Updated Queue')
        self.assertEqual(self.queue.description, 'Updated description')
        self.assertTrue(self.queue.is_closed)
        self.assertEqual(self.queue.status, 'busy')

    def test_edit_queue_status_update(self):
        """Test that the queue status can be updated correctly."""
        self.queue.edit(status='full')
        self.assertEqual(self.queue.status, 'full')



class RestaurantQueueModelTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testtest', password='hackme11')

    def test_restaurant_queue_creation(self):
        """Test that a RestaurantQueue can be created with default values."""
        queue = RestaurantQueue.objects.create(
            name="Test Restaurant Queue",
            description="A restaurant queue.",
            created_by=self.user,
            category='restaurant'
        )

        self.assertEqual(queue.name, "Test Restaurant Queue")
        self.assertEqual(queue.description, "A restaurant queue.")
        self.assertEqual(queue.created_by, self.user)
        self.assertEqual(queue.has_outdoor, False)

    def test_adding_tables_to_queue(self):
        """Test that tables can be added to a RestaurantQueue."""
        queue = RestaurantQueue.objects.create(
            name="Test Restaurant Queue",
            description="A queue for testing purposes.",
            created_by=self.user,
            category='restaurant'
        )

        table1 = Table.objects.create(name="Table 1", capacity=4)
        table2 = Table.objects.create(name="Table 2", capacity=2)

        queue.tables.add(table1)
        queue.tables.add(table2)

        self.assertIn(table1, queue.tables.all())
        self.assertIn(table2, queue.tables.all())
        self.assertEqual(queue.tables.count(), 2)

    def test_has_outdoor_field(self):
        """Test that the has_outdoor field can be set and retrieved correctly."""
        queue = RestaurantQueue.objects.create(
            name="Test Restaurant Queue",
            description="A queue for testing purposes.",
            created_by=self.user,
            category='restaurant',
            has_outdoor=True
        )

        self.assertTrue(queue.has_outdoor)


class TableModelTests(TestCase):

    def setUp(self):
        """Create a user, queue, and a table for testing."""
        self.user = User.objects.create(username='testuser')
        self.queue = Queue.objects.create(
            name='Test Queue',
            description='A test queue',
            created_by=self.user,
            category='restaurant'
        )
        self.table = Table.objects.create(name='Table 1', capacity=4)

    def test_assign_to_party_success(self):
        """Test assigning a table to a party when it is empty and capacity matches."""
        participant = RestaurantParticipant.objects.create(queue=self.queue,
                                                           party_size=2)
        self.table.assign_to_party(participant)

        self.assertEqual(self.table.status, 'busy')
        self.assertEqual(self.table.party, participant)
        self.assertEqual(participant.table, self.table)

    def test_assign_to_party_table_busy(self):
        """Test that assigning a party to a busy table raises an error."""
        participant1 = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)
        participant2 = RestaurantParticipant.objects.create(queue=self.queue, party_size=3)

        self.table.assign_to_party(participant1)

        with self.assertRaises(ValueError):
            self.table.assign_to_party(participant2)

    def test_assign_to_party_incompatible_capacity(self):
        """Test that assigning a party larger than the table's capacity raises an error."""
        participant = RestaurantParticipant.objects.create(queue=self.queue, party_size=5)

        with self.assertRaises(ValueError):
            self.table.assign_to_party(participant)

    def test_free_table(self):
        """Test freeing a busy table."""
        participant = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)
        self.table.assign_to_party(participant)

        self.table.free()
        self.assertEqual(self.table.status, 'empty')
        self.assertIsNone(self.table.party)

    def test_is_assigned(self):
        """Test checking if the table is assigned."""
        participant = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)

        self.assertFalse(self.table.is_assigned())
        self.table.assign_to_party(participant)
        self.assertTrue(self.table.is_assigned())

    def test_change_party(self):
        """Test changing the party assigned to a table."""
        participant1 = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)
        participant2 = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)

        self.table.assign_to_party(participant1)
        self.table.change_party(participant2)

        self.assertEqual(self.table.party, participant2)
        self.assertEqual(self.table.status, 'busy')

    def test_change_party_different_queue(self):
        """Test changing to a party from a different queue raises an error."""
        different_queue = Queue.objects.create(name='Different Queue', description='Another queue',
                                               created_by=self.user, category='restaurant')
        participant1 = RestaurantParticipant.objects.create(queue=self.queue, party_size=2)
        participant2 = RestaurantParticipant.objects.create(queue=different_queue, party_size=2)

        self.table.assign_to_party(participant1)

        with self.assertRaises(ValueError):
            self.table.change_party(participant2)