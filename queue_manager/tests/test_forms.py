import unittest

from django.test import TestCase
from queue_manager.forms import QueueForm


class QueueFormTest(TestCase):
    def test_queue_form_valid_data(self):
        """Test that the form is valid with correct data."""
        form_data = {
            'name': 'Test Queue',
            'description': 'This is a test queue description.',
            'capacity': 10,
            'estimated_wait_time': 10,
            'category': 'restaurant'
        }
        form = QueueForm(data=form_data)
        self.assertTrue(form.is_valid())  # The form should be valid

    def test_queue_form_invalid_data(self):
        """Test that the form is invalid with missing data."""
        form_data = {
            'name': '',
            'description': '',
            'capacity': 10,
            'estimated_wait_time': 'Ten',
        }
        form = QueueForm(data=form_data)
        self.assertFalse(form.is_valid())  # The form should be invalid
        self.assertIn('name', form.errors)  # Check for specific field errors

    def test_queue_form_field_attributes(self):
        """Test the form field attributes."""
        form = QueueForm()
        self.assertEqual(form.fields['name'].widget.attrs['class'], 'form-control')
        self.assertEqual(form.fields['name'].widget.attrs['placeholder'], 'Enter Queue Name (Max Length: 50)')
        self.assertEqual(form.fields['description'].widget.attrs['class'], 'form-control')
        self.assertEqual(form.fields['description'].widget.attrs['rows'], 4)
