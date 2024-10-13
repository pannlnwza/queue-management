from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User
from mysite import settings


class SignupTest(TestCase):
    def test_signup_page_status_code(self):
        """Test that signup page returns a 200 status code."""
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

    def test_signup_valid_data(self):
        """Test that a valid form submission creates a new user."""
        response = self.client.post(reverse('signup'), {
            'username': 'testuser',
            'password1': 'testpassword123',
            'password2': 'testpassword123'
        })
        self.assertEqual(response.status_code, 302)  # Should redirect after successful signup
        user = User.objects.filter(username='testuser').first()
        self.assertIsNotNone(user)  # Check that the user was created
