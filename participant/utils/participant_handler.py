from abc import ABC, abstractmethod
from participant.models import RestaurantParticipant, Participant
from manager.models import Resource, RestaurantQueue, Queue
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


class GeneralParticipantHandler(ParticipantHandler):
    def create_participant(self, data):
        return Participant.objects.create(**data)


class RestaurantParticipantHandler(ParticipantHandler):
    def create_participant(self, data):
        return RestaurantParticipant.objects.create(**data)


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