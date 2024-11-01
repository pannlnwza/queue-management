from django.contrib import admin
from manager.models import Queue
from participant.models import Participant

admin.site.register(Queue)
admin.site.register(Participant)

