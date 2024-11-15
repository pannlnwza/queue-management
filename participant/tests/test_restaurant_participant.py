from django.test import TestCase
from manager.models import *
from manager.utils.category_handler import CategoryHandlerFactory
from participant.models import RestaurantParticipant


class RestaurantParticipantTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser',
                                             password='testpass')

        self.handler = CategoryHandlerFactory.get_handler('restaurant')

        self.queue = self.handler.create_queue({
            'name': 'Restaurant Queue',
            'description': 'A restaurant test queue.',
            'created_by': self.user,
            'estimated_wait_time_per_turn': 5,
            'average_service_duration': 10,
            'longitude': 100.5163,
            'latitude': 13.7285,
        })

    def test_create_participant(self):
        self.participant_1 = self.handler.create_participant({
            'name': 'Taro',
            'email': 'taro@gmail.com',
            'phone': '086-456-8611',
            'note': "I'm sick achoo",
            'queue': self.queue,
            'special_1': 1,
            'special_2': 'first_available',
        }
        )
        self.assertIsInstance(self.participant_1, RestaurantParticipant)
