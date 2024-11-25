import os
from unittest.mock import patch

from django.test import TestCase
from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.templatetags.static import static
from allauth.socialaccount.models import SocialAccount
from manager.models import UserProfile


class UserProfileTests(TestCase):
    def setUp(self):
        # Create a user
        self.user = User.objects.create_user(username="testuser", password="testpassword")

    def test_get_profile_image_uploaded_image(self):
        """Test returning the uploaded profile image."""
        # Create a user profile with an uploaded image
        profile_image = SimpleUploadedFile("test_image.jpg", b"file_content", content_type="image/jpeg")
        self.user.userprofile.image = profile_image
        profile_url = self.user.userprofile.get_profile_image()

        self.assertIn("test_image.jpg", profile_url)

    from unittest.mock import patch

    def test_get_profile_image_social_account(self):
        """Test returning the avatar URL from a social account."""
        # Create a social account for the user
        social_account = SocialAccount.objects.create(user=self.user, provider="google")

        # Mock the `get_avatar_url` method on the SocialAccount class
        with patch('allauth.socialaccount.models.SocialAccount.get_avatar_url',
                   return_value="https://lh3.googleusercontent.com/a/ACg8ocK8696Ka3o2u9cNpBEBcmoGBGk69WNSXxMYVw8flvNgVio8c8mn=s96-c"):
            user_profile = self.user.userprofile

            # Assert the social account avatar URL is returned
            self.assertEqual(user_profile.get_profile_image(),
                             "https://lh3.googleusercontent.com/a/ACg8ocK8696Ka3o2u9cNpBEBcmoGBGk69WNSXxMYVw8flvNgVio8c8mn=s96-c")

    def test_get_profile_image_default(self):
        """Test returning the default profile image."""
        # The UserProfile is already created by the signal
        user_profile = self.user.userprofile

        # Assert the default profile image URL is returned
        self.assertEqual(user_profile.get_profile_image(), static("participant/images/profile.jpg"))

    def test_create_user_profile_signal(self):
        """Test that a UserProfile is created when a new User is created."""
        user = User.objects.create_user(username="newuser", password="newpassword")
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_save_user_profile_signal_with_missing_profile(self):
        """Test that the save_user_profile signal creates a UserProfile if it does not exist."""
        # Create a user
        user = User.objects.create_user(username="missingprofileuser", password="testpassword")

        # Manually delete the UserProfile to simulate the missing profile
        UserProfile.objects.filter(user=user).delete()

        # Save the user to trigger the save_user_profile signal
        user.save()

        # Assert that the UserProfile is re-created
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def tearDown(self):
        """Clean up test files."""
        user_profile = self.user.userprofile
        if user_profile.image and os.path.isfile(user_profile.image.path):
            os.remove(user_profile.image.path)