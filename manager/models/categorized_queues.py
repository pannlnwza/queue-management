from django.db import models
from .queue import Queue
from .resource import Table, Counter, Doctor


class RestaurantQueue(Queue):
    """Represents a queue specifically for restaurant."""
    resources = models.ManyToManyField(Table)
    resource_name = 'Tables'


class BankQueue(Queue):
    """Represents a queue specifically for bank services."""
    resources = models.ManyToManyField(Counter)
    resource_name = 'Counters'

    def __str__(self):
        return f"Bank Queue: {self.name}"


class HospitalQueue(Queue):
    """Represents a queue specifically for hospital services."""
    resources = models.ManyToManyField(Doctor)
    resource_name = 'Doctors'
