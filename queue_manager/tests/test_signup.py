from django.test import TestCase
from django.urls import reverse
from django.contrib.auth.models import User


class SignupTest(TestCase):
    """
    Tests for the signup functionality.
    """

    def test_signup_page_status_code(self):
        """
        Test that the signup page returns a 200 status code.
        """
        response = self.client.get(reverse('signup'))
        self.assertEqual(response.status_code, 200)

    def test_signup_valid_data(self):
        """
        Test that a valid form submission creates a new user.
        """
        response = self.client.post(reverse('signup'), {
            'username': 'testuser',
            'password1': 'testpassword123',
            'password2': 'testpassword123'
        })
        self.assertEqual(response.status_code, 302)
        user = User.objects.filter(username='testuser').first()
        self.assertIsNotNone(user)