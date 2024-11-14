from django.contrib import admin
from participant.models import *

admin.site.register(Participant)
admin.site.register(RestaurantParticipant)
admin.site.register(HospitalParticipant)
admin.site.register(BankParticipant)
admin.site.register(Notification)