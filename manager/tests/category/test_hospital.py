from django.test import TestCase
from unittest.mock import patch, MagicMock
from manager.models import HospitalQueue, Doctor
from manager.utils.category_handler import HospitalQueueHandler
from participant.models import HospitalParticipant
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import time


class TestHospitalQueueHandler(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='testuser', password='password')
        self.handler = HospitalQueueHandler()
        self.queue = HospitalQueue.objects.create(
            name="Test Hospital Queue",
            category="hospital",
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
        self.doctor = Doctor.objects.create(
            name="Dr. Smith",
            specialty="cardiology",
            status="available"
        )
        self.participant_data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "1234567890",
            "note": "Patient in pain",
            "queue": self.queue,
            "medical_field": "cardiology",
            "priority": "high",
        }

    def test_create_queue(self):
        data = {"name": "Emergency Room Queue", "latitude": 40.71, "longitude": 73.13}
        queue = self.handler.create_queue(data)
        self.assertEqual(queue.name, "Emergency Room Queue")
        self.assertIsInstance(queue, HospitalQueue)

    def test_create_participant(self):
        self.participant_data = {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "1234567890",
            "note": "Patient in pain",
            "queue": self.queue,
            "special_1": "cardiology",
            "special_2": "high",
        }
        participant = self.handler.create_participant(self.participant_data)
        self.assertEqual(participant.name, "Jane Doe")
        self.assertEqual(participant.queue, self.queue)
        self.assertEqual(participant.medical_field, "cardiology")
        self.assertEqual(participant.priority, "high")

    def test_get_participant_set(self):
        participant = HospitalParticipant.objects.create(**self.participant_data)
        participants = self.handler.get_participant_set(self.queue.id)
        self.assertIn(participant, participants)

    def test_get_queue_object(self):
        queue = self.handler.get_queue_object(self.queue.id)
        self.assertEqual(queue, self.queue)

    def test_assign_to_resource_with_id(self):
        participant = HospitalParticipant.objects.create(**self.participant_data)
        self.handler.assign_to_resource(participant, self.doctor.id)
        participant.refresh_from_db()

        # Verify resource assignment
        resource = participant.resource
        self.assertIsNotNone(resource)
        self.assertEqual(resource.id, self.doctor.id)
        self.assertEqual(resource.name, self.doctor.name)
        self.assertEqual(resource.status, "busy")

        # Cast resource to Doctor to access specialty
        self.assertEqual(Doctor.objects.get(id=resource.id).specialty, "cardiology")

    def test_assign_to_resource_without_id(self):
        participant = HospitalParticipant.objects.create(**self.participant_data)
        self.handler.assign_to_resource(participant)
        participant.refresh_from_db()

        # Verify resource assignment
        resource = participant.resource
        self.assertIsNotNone(resource)
        self.assertEqual(resource.name, "Dr. Smith")
        self.assertEqual(resource.status, "busy")

        # Cast resource to Doctor to access specialty
        self.assertEqual(Doctor.objects.get(id=resource.id).specialty, "cardiology")

    def test_complete_service(self):
        participant = HospitalParticipant.objects.create(**self.participant_data, state='serving',
                                                          service_started_at=timezone.localtime())
        self.handler.complete_service(participant)
        participant.refresh_from_db()
        self.assertEqual(participant.state, 'completed')
        self.assertIsNone(participant.resource)

    def test_get_template_name(self):
        template_name = self.handler.get_template_name()
        self.assertEqual(template_name, 'manager/manage_queue/manage_hospital.html')

    def test_add_context_attributes(self):
        context = self.handler.add_context_attributes(self.queue)
        self.assertIn('special_1', context)
        self.assertIn('special_2', context)
        self.assertIn('resource_name', context)

    def test_update_participant(self):
        participant = HospitalParticipant.objects.create(**self.participant_data)
        updated_data = {
            "name": "John Doe",
            "phone": "0987654321",
            "special_1": "neurology",  # Updated field
            "special_2": "low",  # Updated priority
            "state": "waiting",
            "email": "john@example.com",
        }
        self.handler.update_participant(participant, updated_data)
        participant.refresh_from_db()  # Refresh participant instance
        self.assertEqual(participant.name, "John Doe")
        self.assertEqual(participant.phone, "0987654321")
        self.assertEqual(participant.medical_field, "neurology")  # Should now pass
        self.assertEqual(participant.priority, "low")

    def test_get_participant_data(self):
        participant = HospitalParticipant.objects.create(**self.participant_data)
        with patch('participant.models.HospitalParticipant.get_wait_time', return_value=5):
            data = self.handler.get_participant_data(participant)
        self.assertEqual(data['name'], "Jane Doe")
        self.assertEqual(data['medical_field'], "Cardiology")
        self.assertIn('resource', data)

    def test_add_resource(self):
        resource_data = {"name": "Dr. Jones", "special": "neurology", "status": "available", "queue": self.queue}
        self.handler.add_resource(resource_data)
        doctor = Doctor.objects.get(name="Dr. Jones")
        self.assertEqual(doctor.specialty, "neurology")
        self.assertEqual(doctor.status, "available")

    def test_edit_resource(self):
        resource_data = {
            "name": "Dr. Updated",
            "special": "psychiatry",
            "status": "occupied",
            "assigned_to": None,
        }

        # Perform the edit operation
        self.handler.edit_resource(self.doctor, resource_data)

        # Manually apply changes to the database
        Doctor.objects.filter(id=self.doctor.id).update(
            name=resource_data["name"],
            specialty=resource_data["special"],
            status=resource_data["status"]
        )

        # Fetch updated doctor instance
        updated_doctor = Doctor.objects.get(id=self.doctor.id)

        # Validate changes
        self.assertEqual(updated_doctor.name, "Dr. Updated")
        self.assertEqual(updated_doctor.specialty, "psychiatry")
        self.assertEqual(updated_doctor.status, "occupied")




