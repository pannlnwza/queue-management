from abc import ABC, abstractmethod
from participant.models import RestaurantParticipant, Participant
from manager.models import Table, RestaurantQueue, Queue
from django.shortcuts import get_object_or_404
from django.utils import timezone


class QueueHandlerFactory:
    @staticmethod
    def get_handler(queue_category):
        if queue_category == 'general':
            return GeneralQueueHandler()
        elif queue_category == 'restaurant':
            return RestaurantQueueHandler()
        # elif queue_category == 'hospital':
        #     return HospitalQueueHandler()
        # elif queue_category == 'bank':
        #     return BankQueueHandler()
        else:
            return GeneralQueueHandler()
            # raise ValueError(f"Unknown category: {queue_category}")


class QueueHandler(ABC):
    # Existing methods...

    @abstractmethod
    def create_queue(self, data):
        """
        Creates a queue specific to the handler's category.
        """
        pass


class GeneralQueueHandler(QueueHandler):
    # Existing methods...

    def create_queue(self, data):
        """
        Creates a general queue.
        """
        return Queue.objects.create(**data)


class RestaurantQueueHandler(QueueHandler):
    # Existing methods...

    def create_queue(self, data):
        """
        Creates a restaurant-specific queue.
        """
        return RestaurantQueue.objects.create(**data)