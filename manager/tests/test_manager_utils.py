import json
from unittest.mock import patch

from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse

from participant.models import RestaurantParticipant, Participant
from manager.models import Table, RestaurantQueue, Queue
from manager.utils.participant_handler import ParticipantHandlerFactory, GeneralParticipantHandler, RestaurantParticipantHandler
from django.utils import timezone


class ParticipantHandlerFactoryTests(TestCase):
    def test_get_handler_general(self):
        handler = ParticipantHandlerFactory.get_handler('general')
        self.assertIsInstance(handler, GeneralParticipantHandler)

    def test_get_handler_restaurant(self):
        handler = ParticipantHandlerFactory.get_handler('restaurant')
        self.assertIsInstance(handler, RestaurantParticipantHandler)

    # def test_get_handler_invalid_category(self):
    #     with self.assertRaises(ValueError):
    #         ParticipantHandlerFactory.get_handler('invalid')


class GeneralParticipantHandlerTests(TestCase):
    def setUp(self):
        self.queue = Queue.objects.create(name="General Queue", description="A general queue")
        self.handler = GeneralParticipantHandler()

    def test_create_participant(self):
        data = {'name': 'Panny 69', 'phone': '1234567890', 'queue': self.queue}
        participant = self.handler.create_participant(data)
        self.assertIsInstance(participant, Participant)
        self.assertEqual(participant.name, 'Panny 69')

    def test_get_participant_set(self):
        data = {'name': 'Panny 69', 'phone': '1234567890', 'queue': self.queue}
        self.handler.create_participant(data)
        participant_set = self.handler.get_participant_set(self.queue.id)
        self.assertEqual(participant_set.count(), 1)

    def test_complete_service(self):
        data = {'name': 'John Doe', 'phone': '1234567890', 'queue': self.queue}
        participant = self.handler.create_participant(data)
        participant.state = 'serving'
        participant.service_started_at = timezone.localtime()
        participant.joined_at = timezone.localtime() - timezone.timedelta(minutes=5)
        participant.save()

        self.handler.complete_service(participant)

        participant.refresh_from_db()
        self.assertEqual(participant.state, 'completed')
        self.assertGreater(participant.service_completed_at, participant.service_started_at)


class RestaurantParticipantHandlerTests(TestCase):
    def setUp(self):
        self.queue = RestaurantQueue.objects.create(name="Restaurant Queue", description="A restaurant queue")
        self.table = Table.objects.create(name="Table 1", capacity=4)
        self.table.save()
        self.queue.tables.add(self.table)
        self.handler = RestaurantParticipantHandler()

    def test_create_participant(self):
        data = {'name': 'Tai Demalu', 'phone': '0987654321', 'queue': self.queue, 'party_size': 2}
        participant = self.handler.create_participant(data)
        self.assertIsInstance(participant, RestaurantParticipant)
        self.assertEqual(participant.name, 'Tai Demalu')

    def test_assign_to_resource(self):
        data = {'name': 'Tai Demalu', 'phone': '0987654321', 'queue': self.queue, 'party_size': 2}
        participant = self.handler.create_participant(data)
        self.handler.assign_to_resource(participant)

        participant.refresh_from_db()
        self.assertEqual(participant.table.status, 'busy')
        self.assertEqual(participant.table.party, participant)

    def test_complete_service(self):
        data = {
            'name': 'Tai Demalu',
            'phone': '0987654321',
            'queue': self.queue,
            'party_size': 2
        }
        participant = self.handler.create_participant(data)

        participant.state = 'serving'
        participant.service_started_at = timezone.localtime()
        participant.joined_at = timezone.localtime() - timezone.timedelta(minutes=5)
        participant.table = self.table
        participant.save()
        participant.refresh_from_db()
        self.handler.complete_service(participant)
        self.assertEqual(participant.state, 'completed')
        self.assertEqual(participant.table, None)
        self.assertEqual(self.table.status, 'empty')
        self.assertEqual(participant.table_served, self.table.name)


class QueueDataTests(TestCase):
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(username='testuser', password='testpass')
        self.queue = Queue.objects.create(created_by=self.user)
        self.restaurant_queue = RestaurantQueue.objects.create(created_by=self.user)

        # Create participants
        self.participant_waiting = Participant.objects.create(
            name='Waiting Participant', queue=self.queue, state='waiting', phone='1234567890'
        )
        self.participant_serving = Participant.objects.create(
            name='Serving Participant', queue=self.queue, state='serving', phone='0987654321'
        )
        self.participant_completed = Participant.objects.create(
            name='Completed Participant', queue=self.queue, state='completed', phone='1112223333'
        )

        self.restaurant_participant_waiting = RestaurantParticipant.objects.create(
            name='Restaurant Waiting Participant', queue=self.restaurant_queue, state='waiting', phone='4445556666'
        )

    def test_get_general_queue_data(self):
        self.client.login(username='testuser', password='testpass')
        url = reverse('manager:get_general_queue_data', args=[self.queue.id])

        # Mock the get_wait_time and get_service_duration methods
        with patch.object(Participant, 'get_wait_time', return_value=10), \
                patch.object(Participant, 'get_service_duration', return_value=5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)

            self.assertIn('waiting_list', data)
            self.assertIn('serving_list', data)
            self.assertIn('completed_list', data)
            self.assertEqual(data['waiting_list'][0]['name'], 'Waiting Participant')
            self.assertEqual(data['serving_list'][0]['name'], 'Serving Participant')
            self.assertEqual(data['completed_list'][0]['name'], 'Completed Participant')

    def test_get_restaurant_queue_data(self):
        self.client.login(username='testuser', password='testpass')
        url = reverse('manager:get_restaurant_queue_data', args=[self.restaurant_queue.id])

        # Mock the methods for restaurant participant
        with patch.object(RestaurantParticipant, 'get_wait_time', return_value=10), \
                patch.object(RestaurantParticipant, 'get_service_duration', return_value=5):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.content)

            self.assertIn('waiting_list', data)
            self.assertIn('serving_list', data)
            self.assertIn('completed_list', data)
            self.assertEqual(data['waiting_list'][0]['name'], 'Restaurant Waiting Participant')