from abc import ABC, abstractmethod
from participant.models import RestaurantParticipant, Participant, HospitalParticipant, BankParticipant
from manager.models import Resource, RestaurantQueue, Queue, BankQueue, HospitalQueue, Doctor
from django.shortcuts import get_object_or_404
from django.utils import timezone


class CategoryHandlerFactory:
    _handlers = {}

    @staticmethod
    def get_handler(queue_id):
        queue = get_object_or_404(Queue, id=queue_id)
        queue_category = queue.category
        if queue_category in CategoryHandlerFactory._handlers:
            return CategoryHandlerFactory._handlers[queue_category]

        if queue_category == 'general':
            handler = GeneralQueueHandler()
        elif queue_category == 'restaurant':
            handler = RestaurantQueueHandler()
        elif queue_category == 'bank':
            handler = BankQueueHandler()
        elif queue_category == 'hospital':
            handler = HospitalQueueHandler()
        else:
            handler = GeneralQueueHandler()

        CategoryHandlerFactory._handlers[queue_category] = handler
        return handler


class CategoryHandler(ABC):
    @abstractmethod
    def create_queue(self, data):
        pass

    @abstractmethod
    def create_participant(self, data):
        pass

    @abstractmethod
    def get_participant_set(self, queue_id):
        pass

    @abstractmethod
    def get_queue_object(self, queue_id):
        pass

    @abstractmethod
    def assign_to_resource(self, participant):
        pass

    @abstractmethod
    def complete_service(self, participant):
        pass

    @abstractmethod
    def add_context_attributes(self, queue):
        """Returns restaurant-specific attributes for the context."""
        pass

    @abstractmethod
    def get_template_name(self):
        """Return the template name specific to the handler's category."""
        pass

    @abstractmethod
    def get_participant_data(self, participant):
        pass

    @abstractmethod
    def update_participant(self, participant, data):
        pass


class GeneralQueueHandler(CategoryHandler):
    def create_queue(self, data):
        """
        Creates a general queue.
        """
        return Queue.objects.create(**data)

    def create_participant(self, data):
        return Participant.objects.create(**data)

    def get_participant_set(self, queue_id):
        return Participant.objects.filter(queue_id=queue_id)

    def get_queue_object(self, queue_id):
        return get_object_or_404(Queue, id=queue_id)

    def assign_to_resource(self, participant):
        pass

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_time = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_time
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
            participant.save()

    def get_template_name(self):
        return 'manager/manage_queue/manage_general.html'

    def add_context_attributes(self, queue):
        pass

    def update_participant(self, participant, data):
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.note = data.get('notes', participant.note)
        participant.save()

    def get_participant_data(self, participant):
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'position': participant.position,
            'notes': participant.note,
            'waited': participant.get_wait_time(),
        }
    def get_special_column(self):
        pass

class RestaurantQueueHandler(CategoryHandler):
    def create_queue(self, data):
        """
        Creates a general queue.
        """
        return Queue.objects.create(**data)

    def create_participant(self, data):
        return RestaurantParticipant.objects.create(**data)

    def get_participant_set(self, queue_id):
        return RestaurantParticipant.objects.filter(queue_id=queue_id).all()

    def get_queue_object(self, queue_id):
        return get_object_or_404(RestaurantQueue, id=queue_id)

    def assign_to_resource(self, participant):
        queue = participant.queue
        resource = queue.get_available_resource(required_capacity=participant.party_size)
        if resource:
            resource.assign_to_participant(participant, capacity=participant.party_size)
        else:
            raise ValueError("No available resources")

    def get_template_name(self):
        return 'manager/manage_queue/manage_unique_category.html'

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.resource:
                participant.resource_assigned = participant.resource.name
                participant.resource.status = 'empty'
                participant.resource.save()
                participant.resource = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
            participant.save()

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        return {
            'special_1': 'Party Size',
            'special_2': 'Seating Preference',
            'resource_name': 'Table',
        }

    def update_participant(self, participant, data):
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.party_size = data.get('party_size', participant.party_size)
        participant.note = data.get('notes', participant.note)
        participant.seating_preference = data.get('seating_preference', participant.seating_preference)

        if participant.state == 'completed':
            table_id = data.get('table')
            table = get_object_or_404(Resource, id=table_id)
            participant.table_served = table.name
        else:
            table_id = data.get('table')
            if table_id:
                table = get_object_or_404(participant.queue.tables, id=table_id)
                table.assign_to_party(participant)
        participant.save()

    def get_participant_data(self, participant):
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'position': participant.position,
            'notes': participant.note,
            'waited': participant.waited if participant.state=='completed' else participant.get_wait_time(),
            'completed': participant.service_completed_at.strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
            'special_1': f"{participant.party_size} people",
            'special_2': participant.get_seating_preference_display(),
            'service_duration': participant.get_service_duration(),
            'served': participant.service_started_at.strftime(
                '%d %b. %Y %H:%M') if participant.service_started_at else None,
            'resource_served': participant.resource_assigned,
            'resource': participant.resource.name if participant.resource else None,
            'resource_id': participant.resource.id if participant.resource else None,
        }

class HospitalQueueHandler(CategoryHandler):
    def create_queue(self, data):
        """
        Creates a hospital queue.
        """
        return HospitalQueue.objects.create(**data)

    def create_participant(self, data):
        """
        Creates a participant for the hospital queue.
        """
        return HospitalParticipant.objects.create(**data)

    def get_participant_set(self, queue_id):
        """
        Returns all participants in a hospital queue.
        """
        return HospitalParticipant.objects.filter(queue_id=queue_id).all()

    def get_queue_object(self, queue_id):
        """
        Fetches the hospital queue by ID.
        """
        return get_object_or_404(HospitalQueue, id=queue_id)

    def assign_to_resource(self, participant):
        """
        Assigns a doctor to a hospital participant based on their medical field and priority.
        """
        queue = self.get_queue_object(participant.queue.id)
        doctor = queue.doctors.filter(specialty=participant.medical_field, status='empty').first()
        if doctor:
            doctor.assign_to_participant(participant)
            participant.resource = doctor
            participant.save()
        else:
            raise ValueError("No available doctor for the specified specialty.")

    def get_template_name(self):
        """
        Returns the template name for the hospital queue management.
        """
        return 'manager/manage_queue/manage_hospital.html'

    def complete_service(self, participant):
        """
        Completes the service for the hospital participant.
        """
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.resource:
                participant.resource_assigned = participant.resource.name
                participant.resource.status = 'empty'
                participant.resource.save()
                participant.resource = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
            participant.save()

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        return {
            'special_1': 'Medical Field Needed',
            'special_2': 'Priority',
            'resource_name': 'Doctor',
            'resources': Doctor.objects.filter(queue=queue)
        }

    def update_participant(self, participant, data):
        """
        Updates participant data like priority, medical field, etc.
        """
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.medical_field = data.get('medical_field', participant.medical_field)
        participant.priority = data.get('priority', participant.priority)

        if participant.state == 'completed':
            doctor_id = data.get('doctor')
            doctor = get_object_or_404(Doctor, id=doctor_id)
            participant.resource = doctor
            participant.resource.status = 'busy'
            participant.save()
        else:
            doctor_id = data.get('doctor')
            if doctor_id:
                doctor = get_object_or_404(participant.queue.doctor_set, id=doctor_id)
                doctor.assign_to_participant(participant)

        participant.save()

    def get_participant_data(self, participant):
        """
        Returns participant data, including medical field and priority.
        """
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'position': participant.position,
            'medical_field': participant.get_medical_field_display(),
            'priority': participant.get_priority_display(),
            'waited': participant.waited if participant.state == 'completed' else participant.get_wait_time(),
            'completed': participant.service_completed_at.strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
            'special_1': participant.get_medical_field_display(),
            'special_2': participant.get_priority_display(),
            'service_duration': participant.get_service_duration(),
            'served': participant.service_started_at.strftime(
                '%d %b. %Y %H:%M') if participant.service_started_at else None,
            'resource_served': participant.resource_assigned,
            'resource': participant.resource.name if participant.resource else None,
            'resource_id': participant.resource.id if participant.resource else None,
        }

    def get_special_column(self):
        """
        Returns special columns to display for hospital participants.
        """
        return 'Required Medical Field', 'Priority'

    def get_resource_name(self):
        """
        Returns the resource name, which for hospital participants is a doctor.
        """
        return 'Doctor'




class BankQueueHandler(CategoryHandler):
    def create_queue(self, data):
        """
        Creates a general queue.
        """
        return BankQueue.objects.create(**data)

    def create_participant(self, data):
        return BankParticipant.objects.create(**data)

    def get_participant_set(self, queue_id):
        return BankParticipant.objects.filter(queue_id=queue_id)

    def get_queue_object(self, queue_id):
        return get_object_or_404(BankQueue, id=queue_id)

    def assign_to_resource(self, participant):
        queue = participant.queue
        resource = queue.get_available_resource()
        if resource:
            resource.assign_to_participant(participant)
        else:
            raise ValueError("No available resources")

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.resource:
                participant.resource_assigned = participant.resource.name
                participant.resource.status = 'empty'
                participant.resource.save()
                participant.resource = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
            participant.save()

    def get_template_name(self):
        return 'manager/manage_queue/manage_bank.html'

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        return {
            'special_1': None,
            'special_2': 'Service Type',
            'resource_name': 'Counter',
        }

    def update_participant(self, participant, data):
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.note = data.get('notes', participant.note)
        participant.save()

    def get_participant_data(self, participant):
        return {
            'id': participant.id,
            'name': participant.name,
            'phone': participant.phone,
            'position': participant.position,
            'special_1': None,
            'special_2': participant.get_service_type_display(),
            'notes': participant.note,
            'waited': participant.waited if participant.state=='completed' else participant.get_wait_time(),
            'completed': participant.service_completed_at.strftime('%d %b. %Y %H:%M') if participant.service_completed_at else None,
            'service_duration': participant.get_service_duration(),
            'served': participant.service_started_at.strftime(
                '%d %b. %Y %H:%M') if participant.service_started_at else None,
            'resource': participant.resource.name if participant.resource else None,
            'resource_id': participant.resource.id if participant.resource else None,
            'resource_served': participant.resource_assigned,
        }
