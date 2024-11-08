from abc import ABC, abstractmethod
from participant.models import RestaurantParticipant, Participant
from manager.models import Table, RestaurantQueue, Queue
from django.shortcuts import get_object_or_404
from django.utils import timezone


class ParticipantHandlerFactory:
    _handlers = {}

    @staticmethod
    def get_handler(queue_category):
        if queue_category in ParticipantHandlerFactory._handlers:
            return ParticipantHandlerFactory._handlers[queue_category]

        if queue_category == 'general':
            handler = GeneralParticipantHandler()
        elif queue_category == 'restaurant':
            handler = RestaurantParticipantHandler()
        else:
            handler = GeneralParticipantHandler()  # default handler

        ParticipantHandlerFactory._handlers[queue_category] = handler
        return handler


class ParticipantHandler(ABC):
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
    def update_participant(self, participant, data):
        pass


class GeneralParticipantHandler(ParticipantHandler):
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


class RestaurantParticipantHandler(ParticipantHandler):
    def create_participant(self, data):
        return RestaurantParticipant.objects.create(**data)

    def get_participant_set(self, queue_id):
        return RestaurantParticipant.objects.filter(queue_id=queue_id).all()

    def get_queue_object(self, queue_id):
        return get_object_or_404(RestaurantQueue, id=queue_id)

    def assign_to_resource(self, participant):
        restaurant_participant = RestaurantParticipant.objects.get(id=participant.id)
        table = self.get_available_table(restaurant_participant)
        if table:
            table.assign_to_party(restaurant_participant)
            restaurant_participant.table = table
            restaurant_participant.save()
        else:
            raise ValueError("No available tables match the party size")

    def get_available_table(self, participant):
        return Table.objects.filter(
            status='empty',
            capacity__gte=participant.party_size
        ).first()

    def get_template_name(self):
        return 'manager/manage_queue/manage_restaurant.html'

    def complete_service(self, participant):
        if participant.state == 'serving':
            if participant.service_started_at:
                wait_duration = int((participant.service_started_at - participant.joined_at).total_seconds() / 60)
                participant.waited = wait_duration
            service_duration = int((timezone.localtime() - participant.service_started_at).total_seconds() / 60)
            participant.service_duration = service_duration
            if participant.table:
                participant.table_served = participant.table.name
                participant.table.status = 'empty'
                participant.table.save()
                participant.table = None
            participant.state = 'completed'
            participant.service_completed_at = timezone.localtime()
            participant.save()

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        return [
            {'tables': queue.tables.all()}
        ]

    def update_participant(self, participant, data):
        participant.name = data.get('name', participant.name)
        participant.phone = data.get('phone', participant.phone)
        participant.party_size = data.get('party_size', participant.party_size)
        participant.note = data.get('notes', participant.note)
        participant.seating_preference = data.get('seating_preference', participant.seating_preference)

        if participant.state == 'completed':
            table_id = data.get('table')
            table = get_object_or_404(Table, id=table_id)
            participant.table_served = table.name
        else:
            table_id = data.get('table')
            if table_id:
                table = get_object_or_404(participant.queue.tables, id=table_id)
                table.assign_to_party(participant)
        participant.save()

# class HospitalParticipantHandler(BaseParticipantHandler):
#     def create_participant(self, data):
#         return HospitalParticipant.objects.create(**data)
#
#     def assign_to_resource(self, participant):
#         # Logic to assign the participant to a doctor
#         doctor = self.get_available_doctor()
#         if doctor:
#             doctor.assign_patient(participant)
#
#     def get_available_doctor(self):
#         # Implement logic to find an available doctor
#         return Doctor.objects.filter(is_available=True).first()
#
# class BankParticipantHandler(BaseParticipantHandler):
#     def create_participant(self, data):
#         return BankParticipant.objects.create(**data)
#
#     def assign_to_resource(self, participant):
#         # Logic to assign the participant to a counter
#         counter = self.get_available_counter()
#         if counter:
#             counter.assign_customer(participant)
#
#     def get_available_counter(self):
#         # Implement logic to find an available counter
#         return BankCounter.objects.filter(status='available').first()

