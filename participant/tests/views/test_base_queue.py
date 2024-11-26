from django.test import TestCase, RequestFactory
from django.urls import reverse
from participant.views import BaseQueueView
from manager.models import Queue
from django.contrib.auth.models import User
from datetime import time


class TestBaseQueueView(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        # Create sample queues
        self.restaurant_queue = Queue.objects.create(
            name="Test Queue",
            category="restaurant",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=47.7128,
            longitude=-54.0060,
        )
        self.bank_queue = Queue.objects.create(
            name="Bank Main Queue",
            category="bank",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=42.7128,
            longitude=-72.0060,
        )
        self.general_queue = Queue.objects.create(
            name="Test general Queue",
            category="general",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=55.7128,
            longitude=-77.0060,
        )

        # Request factory for simulating requests
        self.factory = RequestFactory()

        # Subclass BaseQueueView to test specific categories
        class RestaurantQueueView(BaseQueueView):
            queue_category = "restaurant"

        self.view_class = RestaurantQueueView

    def test_get_queryset(self):
        # Simulate a request
        request = self.factory.get(reverse("participant:restaurant_queues"))

        # Instantiate the view and attach the request
        view = self.view_class()
        view.request = request

        # Get the queryset
        queryset = view.get_queryset()

        # Assert the queryset contains only restaurant queues
        self.assertEqual(len(queryset), 1)
        self.assertIn(self.restaurant_queue, queryset)
        self.assertNotIn(self.bank_queue, queryset)
        self.assertNotIn(self.general_queue, queryset)

    def test_get_context_data(self):
        # Simulate a request
        request = self.factory.get(reverse("participant:restaurant_queues"))

        # Instantiate the view and attach the request
        view = self.view_class()
        view.request = request

        # Populate object_list by calling get_queryset
        view.object_list = view.get_queryset()

        # Fetch the context
        context = view.get_context_data()

        # Assert the context contains the correct queue_type and queues
        self.assertEqual(context["queue_type"], "Restaurant")
        self.assertIn(self.restaurant_queue, context["queues"])
        self.assertNotIn(self.bank_queue, context["queues"])
        self.assertNotIn(self.general_queue, context["queues"])
