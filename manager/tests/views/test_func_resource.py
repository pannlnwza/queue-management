from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from manager.models import Resource, Queue
from unittest.mock import patch, MagicMock
from datetime import time


class ResourceViewTests(TestCase):
    def setUp(self):
        # Create a test user
        self.user = User.objects.create_user(username='testuser', password='password')
        self.client = Client()
        self.client.login(username='testuser', password='password')

        # Create a test queue
        self.queue = Queue.objects.create(
            name="Test Queue",
            category="general",
            created_by=self.user,
            open_time=time(8, 0),
            close_time=time(18, 0),
            estimated_wait_time_per_turn=5,
            average_service_duration=10,
            is_closed=False,
            status="normal",
            latitude=40.7128,
            longitude=-74.0060,
        )
        # Create a test resource
        self.resource = Resource.objects.create(
            name="Test Resource",
            queue=self.queue,
            status="active"
        )

        # Patch CategoryHandlerFactory
        self.patcher = patch('manager.utils.category_handler.CategoryHandlerFactory.get_handler')
        self.mock_handler_factory = self.patcher.start()
        self.mock_handler = MagicMock()
        self.mock_handler_factory.return_value = self.mock_handler

    def tearDown(self):
        self.patcher.stop()

    # def test_edit_resource(self):
    #     # Post request to edit resource
    #     response = self.client.post(reverse('manager:resources', args=[self.resource.id]), {
    #         'name': 'Updated Resource',
    #         'special': 'Updated Special Notes',
    #         'assigned_to': 'testuser',
    #         'status': 'inactive',
    #     })
    #
    #     # Assert redirection to resources view
    #     self.assertEqual(response.status_code, 302)
    #     self.assertRedirects(response, reverse('manager:edit_resource', args=[self.queue.id]))
    #
    #     # Verify handler interactions
    #     self.mock_handler_factory.assert_called_once_with(self.queue.category)
    #     self.mock_handler.edit_resource.assert_called_once_with(
    #         self.resource,
    #         {
    #             'name': 'Updated Resource',
    #             'special': 'Updated Special Notes',
    #             'assigned_to': 'testuser',
    #             'status': 'inactive',
    #         }
    #     )
    #
    #     # Verify database state
    #     resource = Resource.objects.get(id=self.resource.id)
    #     self.assertEqual(resource.name, 'Updated Resource')
    #     self.assertEqual(resource.status, 'inactive')
    #
    # def test_add_resource(self):
    #     # Post request to add resource
    #     response = self.client.post(reverse('manager:resources', args=[self.queue.id]), {
    #         'name': 'New Resource',
    #         'special': 'New Special Notes',
    #         'status': 'active',
    #     })
    #
    #     # Assert redirection to resources view
    #     self.assertEqual(response.status_code, 302)
    #     self.assertRedirects(response, reverse('manager:add_resource', args=[self.queue.id]))
    #
    #     # Verify handler interactions
    #     self.mock_handler_factory.assert_called_once_with(self.queue.category)
    #     self.mock_handler.add_resource.assert_called_once_with({
    #         'name': 'New Resource',
    #         'special': 'New Special Notes',
    #         'status': 'active',
    #         'queue': self.queue,
    #     })
    #
    #     # Verify database state
    #     resource = Resource.objects.get(name="New Resource")
    #     self.assertEqual(resource.status, 'active')
    #     self.assertEqual(resource.queue, self.queue)
    #
    def test_delete_resource(self):
        # Delete request for resource
        response = self.client.delete(reverse('manager:delete_resource', args=[self.resource.id]))

        # Assert successful deletion
        self.assertEqual(response.status_code, 200)
        self.assertJSONEqual(response.content, {'message': 'Resource deleted successfully.'})
        self.assertFalse(Resource.objects.filter(id=self.resource.id).exists())

    def test_delete_resource_unauthorized(self):
        # Create another user and login
        other_user = User.objects.create_user(username='otheruser', password='password')
        self.client.logout()
        self.client.login(username='otheruser', password='password')

        # Attempt to delete resource
        response = self.client.delete(reverse('manager:delete_resource', args=[self.resource.id]))

        # Assert unauthorized response
        self.assertEqual(response.status_code, 403)
        self.assertJSONEqual(response.content, {'error': 'Unauthorized.'})
        self.assertTrue(Resource.objects.filter(id=self.resource.id).exists())

    def test_queue_and_resource_relationship(self):
        # Test the relationship between Queue and Resource
        resources = self.queue.resource_set.all()
        self.assertIn(self.resource, resources)
        self.assertEqual(resources.count(), 1)

        # Add another resource to the same queue
        Resource.objects.create(name="Another Resource", queue=self.queue, status="inactive")
        self.assertEqual(self.queue.resource_set.count(), 2)
