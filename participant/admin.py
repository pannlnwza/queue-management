from django.contrib import admin
from participant.models import *
# Register your models here.

admin.site.register(Participant)
admin.site.register(RestaurantParticipant)
admin.site.register(HospitalParticipant)
admin.site.register(BankParticipant)
