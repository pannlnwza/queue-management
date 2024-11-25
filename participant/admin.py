from django.contrib import admin
from participant.models import Participant, RestaurantParticipant, HospitalParticipant, BankParticipant, Notification

admin.site.register(Participant)
admin.site.register(RestaurantParticipant)
admin.site.register(HospitalParticipant)
admin.site.register(BankParticipant)
admin.site.register(Notification)