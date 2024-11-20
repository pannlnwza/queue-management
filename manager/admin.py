from django.contrib import admin
from manager.models import Queue, RestaurantQueue, BankQueue, HospitalQueue, Resource, Doctor, Table, Counter, UserProfile
# Register your models here.

admin.site.register(Queue)
admin.site.register(RestaurantQueue)
admin.site.register(BankQueue)
admin.site.register(HospitalQueue)
admin.site.register(Resource)
admin.site.register(Doctor)
admin.site.register(Table)
admin.site.register(Counter)
admin.site.register(UserProfile)
