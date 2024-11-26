from unittest.mock import patch
from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.conf import settings
from manager.models import Queue, UserProfile
import tempfile
import shutil
import os
from PIL import Image
import io


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class EditProfileViewTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.media_root = tempfile.mkdtemp()
        settings.MEDIA_ROOT = cls.media_root

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.media_root, ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.client = Client()
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpass',
            email='testuser@example.com'
        )
        self.client.login(username='testuser', password='testpass')

        # Create test queue
        self.queue = Queue.objects.create(
            name='Test Queue',
            created_by=self.user,
            category='test_category',
            latitude=0.0,
            longitude=0.0
        )

        # Create user profile
        self.user_profile, _ = UserProfile.objects.get_or_create(
            user=self.user,
            defaults={
                "phone": "123456789",
                "image": "profile_images/default.jpg",
            }
        )

        self.edit_profile_url = reverse('manager:edit_profile',
                                        kwargs={'queue_id': self.queue.id})
    @classmethod
    def create_test_image(cls):
        """Create a test image file"""
        file = io.BytesIO()
        image = Image.new('RGB', (100, 100), 'white')
        image.save(file, 'JPEG')
        file.seek(0)
        return SimpleUploadedFile(
            "test_image.jpg",
            file.getvalue(),
            content_type="image/jpeg"
        )

    def test_get_edit_profile(self):
        """Test GET request to edit profile page"""
        response = self.client.get(self.edit_profile_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'manager/edit_profile.html')

    @patch('manager.views.CategoryHandlerFactory.get_handler')
    def test_get_context_data(self, mock_handler_factory):
        mock_handler = mock_handler_factory.return_value
        mock_handler.get_queue_object.return_value = self.queue

        response = self.client.get(self.edit_profile_url)

        # Assert queue and context data are set correctly
        self.assertEqual(response.context['queue'], self.queue)
        self.assertEqual(response.context['queue_id'], self.queue.id)
        self.assertEqual(response.context['user'], self.user)

    def test_form_valid_upload_image(self):
        """Test image upload in edit profile form"""
        # Create a real test image
        image_file = self.create_test_image()

        # Prepare form data
        form_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "phone": "123456789",
            "first_name": "Test",
            "last_name": "User",
            "remove_image": "false",
        }

        # Use multipart form data for file upload
        response = self.client.post(
            self.edit_profile_url,
            data={**form_data, 'image': image_file},
            format='multipart'
        )

        # Verify response
        self.assertEqual(response.status_code, 302)  # Should redirect on success

        # Refresh user profile from database
        self.user_profile.refresh_from_db()

        # Verify image was saved
        self.assertIsNotNone(self.user_profile.image)
        self.assertTrue(
            self.user_profile.image.name.endswith('.jpg'),
            f"Image name doesn't end with .jpg: {self.user_profile.image.name}"
        )

        # Verify the image file exists
        self.assertTrue(
            os.path.exists(os.path.join(settings.MEDIA_ROOT, self.user_profile.image.name)),
            f"Image file doesn't exist at {self.user_profile.image.name}"
        )

    def test_remove_profile_image(self):
        """Test removing profile image"""
        # First upload an image
        initial_image = self.create_test_image()
        self.user_profile.image = initial_image
        self.user_profile.save()

        # Then remove it
        form_data = {
            "username": "testuser",
            "email": "testuser@example.com",
            "phone": "123456789",
            "remove_image": "true",
        }

        response = self.client.post(self.edit_profile_url, data=form_data)

        # Refresh user profile
        self.user_profile.refresh_from_db()

        # Verify the image was reset to default
        self.assertEqual(self.user_profile.image, 'profile_images/profile.jpg')
        self.assertIsNone(self.user_profile.google_picture)

    def test_update_profile_information(self):
        """Test updating profile information without image changes"""
        form_data = {
            "username": "newusername",
            "email": "newemail@example.com",
            "phone": "987654321",
            "first_name": "New",
            "last_name": "Name",
            "remove_image": "false",
        }

        response = self.client.post(self.edit_profile_url, data=form_data)

        # Refresh user and profile from database
        self.user.refresh_from_db()
        self.user_profile.refresh_from_db()

        # Verify updates
        self.assertEqual(self.user.username, "newusername")
        self.assertEqual(self.user.email, "newemail@example.com")
        self.assertEqual(self.user.first_name, "New")
        self.assertEqual(self.user.last_name, "Name")
        self.assertEqual(self.user_profile.phone, "987654321")

    def test_invalid_form_submission(self):
        """Test form submission with invalid data"""
        form_data = {
            "username": "",
            "email": "invalid-email",
        }

        response = self.client.post(self.edit_profile_url, data=form_data)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].errors)
