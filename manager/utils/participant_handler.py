from abc import ABC, abstractmethod
from participant.models import RestaurantParticipant
from manager.models import Table, RestaurantQueue
from django.shortcuts import get_object_or_404

class ParticipantHandlerFactory:
    @staticmethod
    def get_handler(queue_category):
        if queue_category == 'restaurant':
            return RestaurantParticipantHandler()
        # elif queue_category == 'hospital':
        #     return HospitalParticipantHandler()
        # elif queue_category == 'bank':
        #     return BankParticipantHandler()
        else:
            raise ValueError(f"Unknown category: {queue_category}")



class ParticipantHandler(ABC):
    @abstractmethod
    def create_participant(self, data):
        pass

    @abstractmethod
    def get_queue_object(self, queue_id):
        pass

    @abstractmethod
    def get_participants(self, queue_id):
        pass

    @abstractmethod
    def assign_to_resource(self, participant):
        pass

    @abstractmethod
    def complete_service(self, participant):
        pass

    @abstractmethod
    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        pass

class RestaurantParticipantHandler(ParticipantHandler):
    def create_participant(self, data):
        return RestaurantParticipant.objects.create(**data)

    def get_queue_object(self, queue_id):
        return get_object_or_404(RestaurantQueue, id=queue_id)

    def get_participants(self, queue_id):
        return RestaurantParticipant.objects.filter(queue_id=queue_id)

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

    def complete_service(self, participant):
        restaurant_participant = RestaurantParticipant.objects.get(id=participant.id)
        if restaurant_participant.table:
            restaurant_participant.table_served = restaurant_participant.table.name
            restaurant_participant.table.status = 'empty'
            restaurant_participant.table.save()
            restaurant_participant.table = None
        restaurant_participant.state = 'completed'
        restaurant_participant.save()

    def add_context_attributes(self, queue):
        """
        Returns restaurant-specific attributes for the context.
        """
        return [
            {'tables': queue.tables.all()}
        ]

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