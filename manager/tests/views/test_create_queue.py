from django.test import TestCase, RequestFactory
from django.urls import reverse
from unittest.mock import patch
from unittest.mock import Mock
from manager.views import MultiStepFormView
from manager.forms import QueueForm, OpeningHoursForm, ResourceForm
from manager.models import Queue
from django.contrib.auth.models import User
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.urls import resolve


class MultiStepFormViewTest(TestCase):
    def setUp(self):
        """Set up test environment."""
        self.factory = RequestFactory()
        self.user = User.objects.create_user(username='testuser', password='password')
        self.view = MultiStepFormView.as_view()

    def add_middleware(self, request):
        """Add session and message middleware to the request."""
        # Add session middleware
        session_middleware = SessionMiddleware(get_response=Mock())
        session_middleware.process_request(request)
        request.session.save()

        # Add message middleware
        message_middleware = MessageMiddleware(get_response=Mock())
        message_middleware.process_request(request)

        return request

    def test_get_step_1(self):
        """Test GET request for step 1."""
        # Simulate a request to the view
        request = self.factory.get(reverse('manager:create_queue_step', args=['1']))
        response = resolve(reverse('manager:create_queue_step', args=['1'])).func(request, step="1")

        # Confirm the response is rendered correctly with a form
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<form')

    # def test_get_step_2(self):
    #     """Test GET request for step 2."""
    #     request = self.factory.get(reverse('manager:create_queue_step', args=['2']))
    #     request = self.add_middleware(request)
    #     request.session['queue_data'] = {'name': 'Test Queue'}
    #     # response = self.view(request, step="2")
    #     response = resolve(reverse('manager:create_queue_step', args=['2'])).func(request, step="2")
    #     self.assertEqual(response.status_code, 200)
    #     self.assertIn('form', response.context_data)
    #     self.assertIsInstance(response.context_data['form'], OpeningHoursForm)
    #
    # def test_get_step_3(self):
    #     """Test GET request for step 3."""
    #     request = self.factory.get(reverse('manager:create_queue_step', args=['3']))
    #     request = self.add_middleware(request)
    #     request.session['queue_data'] = {'category': 'Test Category'}
    #     # response = self.view(request, step="3")
    #     response = resolve(reverse('manager:create_queue_step', args=['3'])).func(request, step="3")
    #     self.assertEqual(response.status_code, 200)
    #     self.assertIn('form', response.context_data)
    #     self.assertIsInstance(response.context_data['form'], ResourceForm)
    #
    # def test_post_step_1_valid(self):
    #     """Test POST request for step 1 with valid data."""
    #     request = self.factory.post(reverse('manager:create_queue_step', args=['1']),
    #                                 data={'name': 'Test Queue'})
    #     request = self.add_middleware(request)
    #     # response = self.view(request, step="1")
    #     response = resolve(reverse('manager:create_queue_step', args=['1'])).func(request, step="1")
    #     self.assertEqual(response.status_code, 302)  # Redirect to step 2
    #     self.assertEqual(request.session['queue_data']['name'], 'Test Queue')
    #
    # def test_post_step_1_invalid(self):
    #     """Test POST request for step 1 with invalid data."""
    #     request = self.factory.post(reverse('manager:create_queue_step', args=['1']), data={})
    #     request = self.add_middleware(request)
    #     # response = self.view(request, step="1")
    #     response = resolve(reverse('manager:create_queue_step', args=['1'])).func(request, step="1")
    #     self.assertEqual(response.status_code, 200)  # Render form again
    #     self.assertIn('form', response.context_data)
    #     self.assertIsInstance(response.context_data['form'], QueueForm)
    #
    # def test_post_step_2_valid(self):
    #     """Test POST request for step 2 with valid data."""
    #     request = self.factory.post(reverse('manager:create_queue_step', args=['2']),
    #                                 data={'open_time': '08:00', 'close_time': '17:00'})
    #     request = self.add_middleware(request)
    #     # response = self.view(request, step="2")
    #     response = resolve(reverse('manager:create_queue_step', args=['2'])).func(request, step="2")
    #     self.assertEqual(response.status_code, 302)  # Redirect to step 3
    #     self.assertIn('time_and_location_data', request.session)
    #
    # def test_post_step_2_invalid(self):
    #     """Test POST request for step 2 with invalid data."""
    #     request = self.factory.post(reverse('manager:create_queue_step', args=['2']), data={})
    #     request = self.add_middleware(request)
    #
    #     response = self.view(request, step="2")
    #     if hasattr(response, 'render'):
    #         response.render()
    #
    #     self.assertEqual(response.status_code, 200)  # Should re-render form
    #     self.assertIn('form', response.context_data)
    #     self.assertTrue(response.context_data['form'].errors)
    #
    # @patch('manager.views.CategoryHandlerFactory.get_handler')
    # def test_post_step_3_valid(self, mock_handler_factory):
    #     """Test POST request for step 3 with valid data."""
    #     # Mock the handler and its methods
    #     mock_handler = mock_handler_factory.return_value
    #     mock_handler.create_queue.return_value = Queue(name="Test Queue")
    #
    #     # Simulate valid POST data for a 'hospital' queue
    #     request = self.factory.post(
    #         reverse('manager:create_queue_step', args=['3']),
    #         data={'name': 'Dr. John', 'status': 'available', 'special': 'Cardiology'}
    #     )
    #     request.user = self.user
    #     request = self.add_middleware(request)
    #
    #     # Provide required session data for a 'hospital' queue category
    #     request.session['queue_data'] = {'category': 'hospital', 'name': 'Test Queue'}
    #     request.session['time_and_location_data'] = {'open_time': '08:00', 'close_time': '17:00'}
    #
    #     # Call the view
    #     response = self.view(request, step="3")
    #     if hasattr(response, 'render'):
    #         response.render()
    #
    #     # Assertions
    #     self.assertEqual(response.status_code, 200)  # Should redirect to queue list
    #     mock_handler.add_resource.assert_called_once_with({
    #         'name': 'Dr. John',
    #         'status': 'available',
    #         'special': 'Cardiology',
    #         'queue': mock_handler.create_queue.return_value
    #     })
    #
    # def test_post_step_3_invalid(self):
    #     """Test POST request for step 3 with invalid data."""
    #     request = self.factory.post(reverse('manager:create_queue_step', args=['3']), data={})
    #     request.user = self.user
    #     request = self.add_middleware(request)
    #     request.session['queue_data'] = {'category': 'Test Category', 'name': 'Test Queue'}
    #     request.session['time_and_location_data'] = {'open_time': '08:00', 'close_time': '17:00'}
    #
    #     # response = self.view(request, step="3")
    #     response = resolve(reverse('manager:create_queue_step', args=['3'])).func(request, step="3")
    #     self.assertEqual(response.status_code, 200)  # Render form again
    #     self.assertIn('form', response.context_data)
    #     self.assertIsInstance(response.context_data['form'], ResourceForm)
