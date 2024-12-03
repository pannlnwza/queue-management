from django.db import models
from .queue import Queue
from .resource import Table, Counter, Doctor


class RestaurantQueue(Queue):
    """
    Represents a restaurant queue with a set of tables as resources.
    """
    resources = models.ManyToManyField(Table)
    resource_name = 'Tables'


class BankQueue(Queue):
    """
    Represents a queue for bank services with counters as resources.
    """
    resources = models.ManyToManyField(Counter)
    resource_name = 'Counters'

    def __str__(self):
        return f"Bank Queue: {self.name}"


class HospitalQueue(Queue):
    """
    Represents a queue for hospital services with doctors as resources.
    """
    resources = models.ManyToManyField(Doctor)
    resource_name = 'Doctors'
