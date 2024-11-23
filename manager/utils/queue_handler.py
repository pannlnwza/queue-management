from abc import ABC, abstractmethod
from manager.models import RestaurantQueue, Queue


class QueueHandlerFactory:
    _handlers = {}

    @staticmethod
    def get_handler(queue_category):
        if queue_category in QueueHandlerFactory._handlers:
            return QueueHandlerFactory._handlers[queue_category]

        if queue_category == 'general':
            handler = GeneralQueueHandler()
        elif queue_category == 'restaurant':
            handler = RestaurantQueueHandler()
        else:
            handler = GeneralQueueHandler()  # default handler

        QueueHandlerFactory._handlers[queue_category] = handler
        return handler


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