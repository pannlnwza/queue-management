from unittest.mock import patch

from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth.models import User
from django.contrib.messages import get_messages
from manager.models import UserProfile
from manager.forms import CustomUserCreationForm
import logging


class TestUserRegistration(TestCase):
    def setUp(self):
        self.client = Client()
        self.signup_url = reverse('signup')
        self.login_url = reverse('login')
        self.home_url = reverse('participant:home')
        self.queue_url = reverse('manager:your-queue')

        logging.disable(logging.CRITICAL)

        self.user_data = {
            'username': 'testuser',
            'email': 'test@example.com',
            'password1': 'TestPassword123!',
            'password2': 'TestPassword123!'
        }

        self.login_data = {
            'username': 'testuser',
            'password': 'TestPassword123!'
        }

    def tearDown(self):
        # Re-enable logging
        logging.disable(logging.NOTSET)

    def test_signup_page_GET(self):
        """Test that signup page loads correctly"""
        response = self.client.get(self.signup_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/signup.html')
        self.assertIsInstance(response.context['form'], CustomUserCreationForm)

    def test_successful_signup_POST(self):
        """Test successful user registration"""
        response = self.client.post(self.signup_url, self.user_data)

        # Check if user was created
        self.assertEqual(User.objects.count(), 1)
        user = User.objects.first()
        self.assertEqual(user.username, self.user_data['username'])

        # Check if UserProfile was created
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

        # Check redirect
        self.assertRedirects(response, self.home_url)

        # Check if user is logged in
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_invalid_signup_POST(self):
        """Test signup with invalid data"""
        # Test with invalid password confirmation
        invalid_data = self.user_data.copy()
        invalid_data['password2'] = 'WrongPassword123!'

        response = self.client.post(self.signup_url, invalid_data)

        # Check that no user was created
        self.assertEqual(User.objects.count(), 0)
        self.assertEqual(response.status_code, 200)

        # Check for form errors
        self.assertTrue(response.context['form'].errors)

    def test_signup_creates_userprofile(self):
        """Test that UserProfile is created with signup"""
        self.client.post(self.signup_url, self.user_data)
        user = User.objects.get(username=self.user_data['username'])
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    @patch('manager.views.authenticate')
    def test_signup_authentication_failure(self, mock_authenticate):
        """Test error handling when authentication after signup fails"""
        # Make authenticate return None to simulate authentication failure
        mock_authenticate.return_value = None

        # Use a valid form submission that would normally succeed
        response = self.client.post(self.signup_url, self.user_data, follow=True)

        # Check that the error message is present
        messages = list(get_messages(response.wsgi_request))
        error_message = 'Error during signup process. Please try again.'
        self.assertTrue(
            any(message.message == error_message for message in messages),
            f"Expected message '{error_message}' not found in messages: {[m.message for m in messages]}"
        )

        # Verify the user was created but not authenticated
        self.assertEqual(User.objects.filter(username=self.user_data['username']).count(), 1)

        # Verify we're not logged in
        self.assertFalse('_auth_user_id' in self.client.session)

        # Verify authenticate was called with correct credentials
        mock_authenticate.assert_called_once_with(
            username=self.user_data['username'],
            password=self.user_data['password1']
        )

        # Check that we stayed on the signup page
        self.assertEqual(response.status_code, 200)

    @patch('manager.models.UserProfile.objects.get_or_create')
    def test_signup_profile_creation_error(self, mock_get_or_create):
        """Test error handling when UserProfile creation fails"""
        # Mock get_or_create to return (None, False) indicating profile creation failure
        mock_get_or_create.return_value = (None, False)

        response = self.client.post(self.signup_url, self.user_data)

        # Check error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any(message.message == 'Error creating user profile. Please contact support.'
                            for message in messages))

class TestUserLogin(TestCase):
    def setUp(self):
        self.client = Client()
        self.login_url = reverse('login')  # Adjust URL name as needed
        self.queue_url = reverse('manager:your-queue')  # Adjust URL name as needed

        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='TestPassword123!'
        )

        self.login_data = {
            'username': 'testuser',
            'password': 'TestPassword123!'
        }

    def test_login_page_GET(self):
        """Test that login page loads correctly"""
        response = self.client.get(self.login_url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'account/login.html')

    def test_successful_login_POST(self):
        """Test successful login"""
        response = self.client.post(self.login_url, self.login_data)

        # Check redirect
        self.assertRedirects(response, self.queue_url)

        # Check if user is logged in
        self.assertTrue('_auth_user_id' in self.client.session)

    def test_invalid_login_POST(self):
        """Test login with invalid credentials"""
        invalid_data = self.login_data.copy()
        invalid_data['password'] = 'WrongPassword123!'

        response = self.client.post(self.login_url, invalid_data)

        # Check that user is not logged in
        self.assertFalse('_auth_user_id' in self.client.session)

        # Check for error message
        messages = list(get_messages(response.wsgi_request))
        self.assertTrue(any(message.message == 'Invalid username or password.'
                            for message in messages))

    def test_login_creates_userprofile_if_needed(self):
        """Test that UserProfile is created if it doesn't exist during login"""
        # Delete UserProfile if it exists
        UserProfile.objects.filter(user=self.user).delete()

        # Login
        self.client.post(self.login_url, self.login_data)

        # Check if UserProfile was created
        self.assertTrue(UserProfile.objects.filter(user=self.user).exists())

    def test_login_with_social_account(self):
        """Test login behavior with social account"""
        # This is a placeholder test - expand based on your social auth implementation
        response = self.client.post(self.login_url, self.login_data)
        self.assertRedirects(response, self.queue_url)